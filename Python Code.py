import codecs
import csv
import re
import schema
import cerberus
import xml.etree.cElementTree as ET



OSM_PATH = "nashville_tennessee.osm"

NODES_PATH = "nodes.csv"
NODE_TAGS_PATH = "nodes_tags.csv"
WAYS_PATH = "ways.csv"
WAY_NODES_PATH = "ways_nodes.csv"
WAY_TAGS_PATH = "ways_tags.csv"

streets = ["Street", "St", "St.", "Avenue", "Ave", "Boulevard", "Blvd", "Drive", "Dr", "Court", "Ct", "Place",
           "Lane", "Ln", "Road", "Rd", "Run", "spur", "Path", "Trail", "Parkway", "Pky", "Pkwy", "Commons", "Pike",
           "Pik", "Alley", "Pl", "Way", "Terrace", "Circle", "Row", "Cv", "Tcre", "Loop", "Hwy", "Br", "Xing", "Plz",
           "Byp", "Pass", "Walk", "Cres", "Ter"]
street_direction = ["North", "N", "South", "S", "East", "E", "West", "W", "NW", "SE", "NE", "SW"]

street_last = re.compile(r'\S+\.?$', re.IGNORECASE)
street_second_last = re.compile(r'\w+\s\w+$', re.IGNORECASE)

streets_re = re.compile(r'\b(?:%s)\b' % '|'.join(streets))
LOWER_COLON = re.compile(r'^([a-z]|_)+:([a-z]|_)+')
PROBLEMCHARS = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')


SCHEMA = schema.schema

# Make sure the fields order in the csvs matches the column order in the sql table schema
NODE_FIELDS = ['id', 'lat', 'lon', 'user', 'uid', 'version', 'changeset', 'timestamp']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']

mapping = { "St": "Street",
            "St.": "Street",
            "Ave": "Avenue",
            "Rd.": "Road",
            "Rd": "Road",
            "Pky": "Parkway",
            "Pkwy": "Parkway",
            "Pl": "Place",
            "Dr": "Drive",
            "Ct": "Court",
            "Pik": "Pike",
            "Blvd": "Boulevard",
            "Cv": "Cove",
            "Trce": "Trace",
            "Hwy": "Highway",
            "Br": "Branch",
            "Ln": "Lane",
            "Xing": "Crossing",
            "Plz": "Plaza",
            "Byp": "Bypass",
            "Cres": "Crescent",
            "Ter": "Terrace"
            }

distinct = set()


def update_name(name):
    """Function to convert the abbreviated street types to their full names using the mapping dictionary"""
    m = street_last.search(name)
    if m.group() in mapping.keys():
        name = name.replace(m.group(),mapping[m.group()])

    return name


def shape_element(element, node_attr_fields=NODE_FIELDS, way_attr_fields=WAY_FIELDS,
                  problem_chars=PROBLEMCHARS, default_tag_type='regular'):
    """Clean and shape node or way XML element to Python dict"""

    node_attribs = {}
    way_attribs = {}
    way_nodes = []
    tags = []  # Handle secondary tags the same way for both node and way elements

    # YOUR CODE HERE

    node_tags = []
    way_tags = []


    if element.tag == 'node':

        # node tags
        for tag in element.iter("tag"):
            node_tags_dict = {}
            node_tags_dict['id'] = element.attrib['id']
            node_tags_dict['value'] = tag.attrib['v']

            colon_split = re.split(r':+?', tag.attrib['k'])
            find_colon = re.findall(r':', tag.attrib['k'])
            after_colon = re.findall(r':.*', tag.attrib['k'])

            if find_colon:
                node_tags_dict['type'] = colon_split[0]
                node_tags_dict['key'] = after_colon[0][1:]
            else:
                node_tags_dict['type'] = 'regular'
                node_tags_dict['key'] = colon_split[0]

            if node_tags_dict['key'] in ('postcode','housenumber'):
                #Extract number-number and exclude other alphanumeric characters
                if re.findall(r'\d+-\d+|\d+', node_tags_dict['value']):
                    node_tags_dict['value'] = re.findall(r'\d+-\d+|\d+', node_tags_dict['value'])[0]

            if node_tags_dict['key'] == 'city':
                # Only keep the city name and exclude the state/county ("Gallatin, TN", "Nashville-Davidson")
                if re.findall(r'\w+\s\w+|\w+', node_tags_dict['value']):
                    node_tags_dict['value'] = re.findall(r'\w+\s\w+|\w+', node_tags_dict['value'])[0]

            node_tags.append(node_tags_dict)

        # node
        node = {}
        for i in range(0, 8):
            if element.attrib[node_attr_fields[i]]:
                node[node_attr_fields[i]] = element.attrib[node_attr_fields[i]]

        node_attribs = node
        tags = node_tags

    if element.tag == 'way':

        # nd tags
        position = 0
        for tag in element.iter("nd"):
            way_nodes_dict = {}
            way_nodes_dict['id'] = element.attrib['id']
            way_nodes_dict['node_id'] = tag.attrib['ref']
            way_nodes_dict['position'] = position
            way_nodes.append(way_nodes_dict)
            position += 1

        # way tags
        street_found = 0
        street_base = None
        street_type = None
        street_dir = None
        way_tags_dict = {}
        for tag in element.iter("tag"):
            way_tags_dict = {}
            way_tags_dict['id'] = element.attrib['id']
            way_tags_dict['value'] = tag.attrib['v']

            colon_split = re.split(r':+?', tag.attrib['k'])
            find_colon = re.findall(r':', tag.attrib['k'])
            after_colon = re.findall(r':.*', tag.attrib['k'])

            if find_colon:
                way_tags_dict['type'] = colon_split[0]
                way_tags_dict['key'] = after_colon[0][1:]

                if way_tags_dict['type'] == 'tiger':#Store name_base, name_type, name_direction_prefix to be used later
                    if way_tags_dict['key'] == 'name_base':
                        street_base = way_tags_dict['value']
                    if way_tags_dict['key'] == 'name_type':
                        street_type = way_tags_dict['value']
                    if way_tags_dict['key'] == 'name_direction_prefix':
                        street_dir = way_tags_dict['value']
            else:
                way_tags_dict['type'] = 'regular'
                way_tags_dict['key'] = colon_split[0]
                if way_tags_dict['key'] == 'name':
                    if streets_re.search(way_tags_dict['value']):   # Check the value contains one of the street type within the string
                        m = street_last.search(way_tags_dict['value'])
                        if m.group() in streets or m.group() in street_direction:# Check if the last word is a street type
                            way_tags_dict['key'] = 'street'
                            way_tags_dict['type'] = 'addr'
                        else:
                            pass    #Check if any other street names remaining that you need to add to the valid street list
                            #distinct.add(m.group())
                    else:
                        pass  # Check if any other street names remaining you need to add to the valid street list
                        # m = street_last.search(way_tags_dict['value'])
                        # distinct.add(m.group())

            if way_tags_dict['key'] == 'street':    #If street is found in the key:name, flag that the street is found
                way_tags_dict['value'] = update_name(way_tags_dict['value'])
                street_found = 1


            if way_tags_dict['key'] in ('postcode','housenumber'):
                #Extract number-number and exclude other characters (like state = 'TN 30307' or housenumber = '417 Woodland St')
                if re.findall(r'\d+-\d+|\d+',way_tags_dict['value']):
                    way_tags_dict['value'] = re.findall(r'\d+-\d+|\d+',way_tags_dict['value'])[0]

            way_tags.append(way_tags_dict)

            if way_tags_dict['key'] == 'city':
                # Only keep the city name and exclude the state/county ("Gallatin, TN", "Nashville-Davidson")
                if re.findall(r'\w+\s\w+|\w+', way_tags_dict['value']):
                    way_tags_dict['value'] = re.findall(r'\w+\s\w+|\w+', way_tags_dict['value'])[0]

        if street_found:
            pass
        else:
            #If there are any streets which are only available in the key:name_base/name_type
            if street_base:
                if street_type in streets:
                    way_tags_dict['id'] = element.attrib['id']
                    way_tags_dict['key'] = 'street'
                    way_tags_dict['type'] = 'addr'

                    if street_dir:                                      # If street direction is available
                        way_tags_dict['value'] = street_dir + ' ' + street_base + ' ' + street_type
                    else:
                        way_tags_dict['value'] = street_base + ' ' + street_type

                    way_tags_dict['value'] = update_name(way_tags_dict['value'])
                    way_tags.append(way_tags_dict)
                # else: # Check if any other street names remaining you need to add to the valid street list
                #     distinct.add(street_type)
                #     if street_type is not None:
                #         print(street_base + ' ' + street_type)

        # way
        way = {}
        for i in range(0, 6):
            if element.attrib[way_attr_fields[i]]:
                way[way_attr_fields[i]] = element.attrib[way_attr_fields[i]]

        way_attribs = way
        tags = way_tags


    if element.tag == 'node':
        return {'node': node_attribs, 'node_tags': tags}
    elif element.tag == 'way':
        return {'way': way_attribs, 'way_nodes': way_nodes, 'way_tags': tags}


# ================================================== #
#               Helper Functions                     #
# ================================================== #
def get_element(osm_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag"""

    context = ET.iterparse(osm_file, events=('start', 'end'))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()



def validate_element(element, validator, schema=SCHEMA):
    """Raise ValidationError if element does not match schema"""
    if validator.validate(element, schema) is not True:
        field, errors = next(validator.errors.iteritems())
        message_string = "\nElement of type '{0}' has the following errors:\n{1}"
        error_string = pprint.pformat(errors)

        raise Exception(message_string.format(field, error_string))


class UnicodeDictWriter(csv.DictWriter, object):
    """Extend csv.DictWriter to handle Unicode input"""

    def writerow(self, row):
        super(UnicodeDictWriter, self).writerow({
                                                    k: (v.encode('utf-8') if isinstance(v, unicode) else v) for k, v in
                                                    row.iteritems()
                                                    })

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


# ================================================== #
#               Main Function                        #
# ================================================== #
def process_map(file_in, validate):
    """Iteratively process each XML element and write to csv(s)"""

    with codecs.open(NODES_PATH, 'w') as nodes_file, \
            codecs.open(NODE_TAGS_PATH, 'w') as nodes_tags_file, \
            codecs.open(WAYS_PATH, 'w') as ways_file, \
            codecs.open(WAY_NODES_PATH, 'w') as way_nodes_file, \
            codecs.open(WAY_TAGS_PATH, 'w') as way_tags_file:

        nodes_writer = UnicodeDictWriter(nodes_file, NODE_FIELDS)
        node_tags_writer = UnicodeDictWriter(nodes_tags_file, NODE_TAGS_FIELDS)
        ways_writer = UnicodeDictWriter(ways_file, WAY_FIELDS)
        way_nodes_writer = UnicodeDictWriter(way_nodes_file, WAY_NODES_FIELDS)
        way_tags_writer = UnicodeDictWriter(way_tags_file, WAY_TAGS_FIELDS)

        nodes_writer.writeheader()
        node_tags_writer.writeheader()
        ways_writer.writeheader()
        way_nodes_writer.writeheader()
        way_tags_writer.writeheader()

        validator = cerberus.Validator()

        for element in get_element(file_in, tags=('node', 'way')):
            el = shape_element(element)


            if el:
                if validate is True:
                    validate_element(el, validator)


                if element.tag == 'node':
                    nodes_writer.writerow(el['node'])
                    node_tags_writer.writerows(el['node_tags'])
                elif element.tag == 'way':
                    ways_writer.writerow(el['way'])
                    way_nodes_writer.writerows(el['way_nodes'])
                    way_tags_writer.writerows(el['way_tags'])


if __name__ == '__main__':
    process_map(OSM_PATH, validate=False)
    #print distinct

