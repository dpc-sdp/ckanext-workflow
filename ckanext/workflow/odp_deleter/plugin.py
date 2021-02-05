import ckan.plugins as p

from ckanext.workflow.odp_deleter import helpers


class ODPDeleter(p.SingletonPlugin):
    '''
    A plugin for deleting datasets from an ODP when deleted from an IAR
    '''
    p.implements(p.IConfigurer)
    p.implements(p.IPackageController, inherit=True)

    # IConfigurer interface #

    def update_config(self, config):
        ''' Setup the template directory '''
        p.toolkit.add_template_directory(config, 'templates')

    # IPackageController interface #

    def after_delete(self, context, pkg_dict):
        # For Data.Vic - when a dataset/package is deleted from the IAR
        # we need to subsequently delete it from the public ODP CKAN instance
        helpers.purge_dataset_from_odp(context, pkg_dict)
        pass

    def after_update(self, context, pkg_dict):
        # For Data.Vic - when a dataset/package is archived from the IAR
        # we need to subsequently delete it from the public ODP CKAN instance
        if pkg_dict.get('workflow_status', None) == 'archived':
            helpers.purge_dataset_from_odp(context, pkg_dict)
        pass
