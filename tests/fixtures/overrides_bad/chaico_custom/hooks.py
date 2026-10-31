app_name = "chaico_custom"
override_doctype_class = {
    "ToDo": "chaico_custom.overrides.CustomToDo",  # no base class at all
    "Task": "chaico_custom.overrides.LocalOnly",  # only inherits from a local class
    "Lead": "erpnext.crm.lead.CustomLead",  # outside this app: unreadable
    "Event": "chaico_custom.overrides.Missing",  # class does not exist
}