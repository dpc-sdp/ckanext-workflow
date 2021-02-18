# ODP Deleter

The purpose of this plugin is to delete datasets from a public CKAN instance 
that harvests from a private CKAN instance, if the dataset on the private 
instance is deleted.

i.e. Open Data Portal (ODP) that harvests public datasets from and Internal 
Asset Register (IAR).

__Note: this plugin will PURGE the datasets from the ODP (i.e. permanently 
delete) - USE WITH CAUTION__

## Configuration

Enable the `odp_deleter` plugin by adding it to your CKAN `.ini` file, e.g.

    ckan.plugins = ... odp_deleter ...

### Environment Variables

The plugin require two environment variables to be set:

#### ODP_API_KEY

#### ODP_URL

