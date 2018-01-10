# CKAN Workflow

This is a simple workflow solution for CKAN. Configuration is available in the form of json config files to set out workflow steps and transitions.

## Installation

To install ``ckanext-workflow``:

Refer to [Extending guide](http://docs.ckan.org/en/latest/extensions/tutorial.html#installing-the-extension)

1. Activate your CKAN virtual environment, for example:

        . /usr/lib/ckan/default/bin/activate

2. Install the ckanext-workflow Python package into your virtual environment:

        cd /usr/lib/ckan/default/src/ckanext-workflow
        python setup.py develop

3. Add ``workflow`` to the ``ckan.plugins`` setting in your CKAN
   config file (by default the config file is located at
   ``/etc/ckan/default/production.ini``).

4. Copy the ``./ckanext-workflow/ckanext/workflow/example.settings.json`` file to your ``/etc/ckan`` directory and name it something like ``workflow.settings.json``

        cd /usr/lib/ckan/default/src/ckanext-workflow
        cp example.settings.json /etc/ckan/workflow.settings.json

5. Add the `ckan.workflow.json_config` config setting to your ``development.ini`` or ``production.ini`` file and set it to the filename used in previous step:

        ckan.workflow.json_config = /etc/ckan/workflow.settings.json

6. Add `datavic_hierarchy_form` to `ckan.plugins` setting in ``development.ini`` and ``production.ini`` files, e.g.

        ckan.plugins = [...] datavic_hierarchy_form

7. Remove the `hierarchy_form` from the `ckan.plugins` setting in ``development.ini`` and ``production.ini`` files, e.g.

8. Restart CKAN. For example if you've deployed CKAN with Apache on Ubuntu:

         sudo service apache2 reload
