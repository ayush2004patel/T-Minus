app_name = "chaico_custom"
override_doctype_class = {
    "ToDo": "chaico_custom.overrides.CustomToDo",
    "Task": ["chaico_custom.overrides.CustomTask"],
}