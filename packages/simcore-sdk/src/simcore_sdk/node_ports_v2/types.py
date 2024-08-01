class PortKey(ConstrainedStr):
    regex = re.compile(PROPERTY_KEY_RE)
