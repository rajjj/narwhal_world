# Naming Guidelines
This guide will help you understand the naming guidelines/conventions used by our organization.

## General Naming Conventions

In general when naming folders please use lowercase letters, as this keeps consistency between developers and makes it easier to use terminal commands.

When naming a file use lowercase letters and <b>DO NOT USE SPACES</b>: <br>
``` Test script.py → UNACCEPTABLE ```

As a globally adopted rule spaces should not be used because each OS treats them differently. Using spaces increases the likelihood that another developer will run into issues when trying to use your files.

Instead of using spaces we use the `_` character. <br>
For example when you need to write out a file such as: <br>
`test program 1.py` → normally this needs spaces <br>
Substitute each space with a underscore: <br>
`test_program_1.py `

### Organization/Company Naming Scheme
A three letter acronym system is used for all projects related to our clients. Using this naming scheme allows for greater confidentiality, it removes bias, and cuts down on long names.
You can more more information naming conventions at: <br>
<https://docs.google.com/document/d/1v9l25suchm1WSp4sxphhZN120Uoz_zgWTF1yGFxz0ww/edit>

## Github Folder Structure

When you create packages in the scripts or flows folder the following folder structure is used: <br>
```scripts/flows folder → 3-letter acronym → salesforce code → poetry package``` <br>

Example: <br>
```root folder → fun → fun69 → fun69_super_processing_prp.py```

### Script Naming Conventions
When naming scripts please add the salesforce code first followed by underscore (\_) and then the extension of the solution type.

Example: <br>
```<salesforce code>_<name>_<extension> --> fun69_verynice_prp.py```

When naming python scripts it is recommended that your script ends with the appropriate extension:

| Solution Type   | Extension expanded | Extension |
|:---------------:|:--------------------------:|:--------------:|
| post-processing | <name\>_post_processing.py  | <name\>_ptp.py  |
| pre-processing  | <name\>_pre_processing.py   | <name\>_prp.py  |
| utility         | utl_<name\>_utility.py      | utl_<name\>.py |

Examples:<br>
```fun69_ohyea_ptp.py → ACCEPTABLE``` <br>
```fun69_ohyea_pos_proc.py → UNACCEPTABLE```
