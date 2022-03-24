# copied from get.py
import ckan.authz as authz
import ckan.lib.navl.dictization_functions as dictization_functions
import ckan.lib.search as search
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import ckan.logic as logic
import logging
import json
from ckanext.workflow import helpers
from ckanext.workflow.logic import queries
from pprint import pprint

_validate = dictization_functions.validate
_check_access = toolkit.check_access
_get_action = toolkit.get_action

log = logging.getLogger(__name__)


@toolkit.side_effect_free
def datavic_package_search(context, data_dict):
    # DEBUG:
    log.debug(helpers.big_separator())
    log.debug("*** datavic_package_search PACKAGE_SEARCH ***")
    '''
    NOTE: This is copied directly from:
    
        /ckan/default/src/ckan/ckan/logic/action/get.py

    And modified for use as per DATAVIC-56:

        https://salsadigital.atlassian.net/browse/DATAVIC-56

    Searches for packages satisfying a given search criteria.

    This action accepts solr search query parameters (details below), and
    returns a dictionary of results, including dictized datasets that match
    the search criteria, a search count and also facet information.

    **Solr Parameters:**

    For more in depth treatment of each paramter, please read the `Solr
    Documentation <http://wiki.apache.org/solr/CommonQueryParameters>`_.

    This action accepts a *subset* of solr's search query parameters:


    :param q: the solr query.  Optional.  Default: ``"*:*"``
    :type q: string
    :param fq: any filter queries to apply.  Note: ``+site_id:{ckan_site_id}``
        is added to this string prior to the query being executed.
    :type fq: string
    :param sort: sorting of the search results.  Optional.  Default:
        ``'relevance asc, metadata_modified desc'``.  As per the solr
        documentation, this is a comma-separated string of field names and
        sort-orderings.
    :type sort: string
    :param rows: the number of matching rows to return. There is a hard limit
        of 1000 datasets per query.
    :type rows: int
    :param start: the offset in the complete result for where the set of
        returned datasets should begin.
    :type start: int
    :param facet: whether to enable faceted results.  Default: ``True``.
    :type facet: string
    :param facet.mincount: the minimum counts for facet fields should be
        included in the results.
    :type facet.mincount: int
    :param facet.limit: the maximum number of values the facet fields return.
        A negative value means unlimited. This can be set instance-wide with
        the :ref:`search.facets.limit` config option. Default is 50.
    :type facet.limit: int
    :param facet.field: the fields to facet upon.  Default empty.  If empty,
        then the returned facet information is empty.
    :type facet.field: list of strings
    :param include_drafts: if ``True``, draft datasets will be included in the
        results. A user will only be returned their own draft datasets, and a
        sysadmin will be returned all draft datasets. Optional, the default is
        ``False``.
    :type include_drafts: boolean
    :param include_private: if ``True``, private datasets will be included in
        the results. Only private datasets from the user's organizations will
        be returned and sysadmins will be returned all private datasets.
        Optional, the default is ``False``.
    :param use_default_schema: use default package schema instead of
        a custom schema defined with an IDatasetForm plugin (default: False)
    :type use_default_schema: bool


    The following advanced Solr parameters are supported as well. Note that
    some of these are only available on particular Solr versions. See Solr's
    `dismax`_ and `edismax`_ documentation for further details on them:

    ``qf``, ``wt``, ``bf``, ``boost``, ``tie``, ``defType``, ``mm``


    .. _dismax: http://wiki.apache.org/solr/DisMaxQParserPlugin
    .. _edismax: http://wiki.apache.org/solr/ExtendedDisMax


    **Examples:**

    ``q=flood`` datasets containing the word `flood`, `floods` or `flooding`
    ``fq=tags:economy`` datasets with the tag `economy`
    ``facet.field=["tags"] facet.limit=10 rows=0`` top 10 tags

    **Results:**

    The result of this action is a dict with the following keys:

    :rtype: A dictionary with the following keys
    :param count: the number of results found.  Note, this is the total number
        of results found, not the total number of results returned (which is
        affected by limit and row parameters used in the input).
    :type count: int
    :param results: ordered list of datasets matching the query, where the
        ordering defined by the sort parameter used in the query.
    :type results: list of dictized datasets.
    :param facets: DEPRECATED.  Aggregated information about facet counts.
    :type facets: DEPRECATED dict
    :param search_facets: aggregated information about facet counts.  The outer
        dict is keyed by the facet field name (as used in the search query).
        Each entry of the outer dict is itself a dict, with a "title" key, and
        an "items" key.  The "items" key's value is a list of dicts, each with
        "count", "display_name" and "name" entries.  The display_name is a
        form of the name that can be used in titles.
    :type search_facets: nested dict of dicts.

    An example result: ::

     {'count': 2,
      'results': [ { <snip> }, { <snip> }],
      'search_facets': {u'tags': {'items': [{'count': 1,
                                             'display_name': u'tolstoy',
                                             'name': u'tolstoy'},
                                            {'count': 2,
                                             'display_name': u'russian',
                                             'name': u'russian'}
                                           ]
                                 }
                       }
     }

    **Limitations:**

    The full solr query language is not exposed, including.

    fl
        The parameter that controls which fields are returned in the solr
        query cannot be changed.  CKAN always returns the matched datasets as
        dictionary objects.
    '''
    # sometimes context['schema'] is None
    schema = (context.get('schema') or
              logic.schema.default_package_search_schema())
    data_dict, errors = _validate(data_dict, schema, context)
    # put the extras back into the data_dict so that the search can
    # report needless parameters
    data_dict.update(data_dict.get('__extras', {}))
    data_dict.pop('__extras', None)
    if errors:
        raise toolkit.ValidationError(errors)

    model = context['model']
    session = context['session']
    user = context.get('user')

    _check_access('package_search', context, data_dict)

    # Move ext_ params to extras and remove them from the root of the search
    # params, so they don't cause and error
    data_dict['extras'] = data_dict.get('extras', {})
    for key in [key for key in data_dict.keys() if key.startswith('ext_')]:
        data_dict['extras'][key] = data_dict.pop(key)

    # check if some extension needs to modify the search params
    for item in plugins.PluginImplementations(plugins.IPackageController):
        data_dict = item.before_search(data_dict)

    # the extension may have decided that it is not necessary to perform
    # the query
    abort = data_dict.get('abort_search', False)

    if data_dict.get('sort') in (None, 'rank'):
        data_dict['sort'] = 'score desc, metadata_modified desc'

    results = []
    if not abort:
        if toolkit.asbool(data_dict.get('use_default_schema')):
            data_source = 'data_dict'
        else:
            data_source = 'validated_data_dict'
        data_dict.pop('use_default_schema', None)
        # return a list of package ids
        data_dict['fl'] = 'id {0}'.format(data_source)

        # we should remove any mention of capacity from the fq and
        # instead set it to only retrieve public datasets
        fq = data_dict.get('fq', '')

        # Remove before these hit solr FIXME: whitelist instead
        include_private = toolkit.asbool(data_dict.pop('include_private', False))
        include_drafts = toolkit.asbool(data_dict.pop('include_drafts', False))

        # DATAVIC-56: Use the controller and action to set search params
        controller_action = '{0}.{1}'.format(toolkit.c.controller, toolkit.c.action)

        capacity_fq = 'capacity:"public"'
        if include_private and authz.is_sysadmin(user):
            capacity_fq, fq = _get_capacity_fq(fq)
        elif controller_action == 'organization.read':
            if 'owner_org:' in fq:
                organization_id = helpers.get_organization_id(data_dict, fq)
            elif 'owner_org' in data_dict.get('q', ''):
                organization_id = helpers.get_organization_id(data_dict, data_dict.get('q', ''))
            else:
                pprint(data_dict)
                import sys
                sys.exit(["I don't know how to handle this yet.", data_dict])

            capacity_fq = queries.organization_read_filter_query(organization_id, user)

            if 'owner_org:' in fq:
                # Remove the `owner_org` from the `fq` search param as we've now used it to
                # reconstruct the search params for Organization view
                fq = ' '.join(p for p in fq.split() if 'owner_org:' not in p)
        elif controller_action == 'dataset.search':
            '''
                DataVic: Implement our own logic for determining the organisational search rules..
            '''
            capacity, fq = _get_capacity_fq(fq)
            query = queries.package_search_filter_query(user)
            capacity_fq = capacity + query if capacity else query
        else:
            # This is the default CKAN search behaviour retained from the core package_search function
            orgs = _get_action('organization_list_for_user')(
                {'user': user}, {'permission': 'read'})
            if orgs:
                capacity_fq = '({0} OR owner_org:({1}))'.format(
                    capacity_fq,
                    ' OR '.join(org['id'] for org in orgs))

        if include_drafts and user:
            capacity_fq = '({0} OR creator_user_id:({1}))'.format(
                capacity_fq,
                authz.get_user_id_for_username(user))

        # DEBUG:
        # if controller_action in ['organization.read', 'dataset.search']:
        #     log.debug('*** DATA_DICT BEFORE capacity_fq ***')
        #     log.debug(pprint(data_dict))
        #     log.debug(helpers.separator())

        if capacity_fq:
            fq = ' '.join(p for p in fq.split() if 'capacity:' not in p)
            data_dict['fq'] = capacity_fq + ' ' + fq

        # DEBUG:
        # if controller_action in ['organization.read', 'dataset.search']:
        #     log.debug('*** DATA_DICT AFTER capacity_fq ***')
        #     log.debug(pprint(data_dict))
        #     log.debug(helpers.separator())

        fq = data_dict.get('fq', '')
        if include_drafts:
            user_id = authz.get_user_id_for_username(user, allow_none=True)
            if authz.is_sysadmin(user):
                data_dict['fq'] = '+state:(active OR draft) ' + fq
            elif user_id:
                # Query to return all active datasets, and all draft datasets
                # for this user.
                u_fq = ' ((creator_user_id:{0} AND +state:(draft OR active))' \
                       ' OR state:active) '.format(user_id)
                data_dict['fq'] = u_fq + ' ' + fq
        elif not authz.is_sysadmin(user):
            data_dict['fq'] = '+state:active ' + fq

        # Pop these ones as Solr does not need them
        extras = data_dict.pop('extras', None)

        query = search.query_for(model.Package)

        # DEBUG:
        # if controller_action in ['organization.read', 'dataset.search']:
        #     log.debug('*** DATA_DICT BEFORE QUERY ***')
        #     log.debug(pprint(data_dict))
        #     helpers.separator()

        query.run(data_dict)

        # Add them back so extensions can use them on after_search
        data_dict['extras'] = extras

        for package in query.results:
            # get the package object
            package_dict = package.get(data_source)
            # use data in search index if there
            if package_dict:
                # the package_dict still needs translating when being viewed
                package_dict = json.loads(package_dict)
                if context.get('for_view'):
                    for item in plugins.PluginImplementations(
                            plugins.IPackageController):
                        package_dict = item.before_view(package_dict)
                results.append(package_dict)
            else:
                log.error('No package_dict is coming from solr for package '
                          'id %s', package['id'])

        count = query.count
        facets = query.facets
    else:
        count = 0
        facets = {}
        results = []

    search_results = {
        'count': count,
        'facets': facets,
        'results': results,
        'sort': data_dict['sort']
    }

    # create a lookup table of group name to title for all the groups and
    # organizations in the current search's facets.
    group_names = []
    for field_name in ('groups', 'organization'):
        group_names.extend(facets.get(field_name, {}).keys())

    groups = (session.query(model.Group.name, model.Group.title)
              .filter(model.Group.name.in_(group_names))
              .all()
              if group_names else [])
    group_titles_by_name = dict(groups)

    # Transform facets into a more useful data structure.
    restructured_facets = {}
    for key, value in facets.items():
        restructured_facets[key] = {
            'title': key,
            'items': []
        }
        for key_, value_ in value.items():
            new_facet_dict = {}
            new_facet_dict['name'] = key_
            if key in ('groups', 'organization'):
                display_name = group_titles_by_name.get(key_, key_)
                display_name = display_name if display_name and display_name.strip() else key_
                new_facet_dict['display_name'] = display_name
            elif key == 'license_id':
                license = model.Package.get_license_register().get(key_)
                if license:
                    new_facet_dict['display_name'] = license.title
                else:
                    new_facet_dict['display_name'] = key_
            else:
                new_facet_dict['display_name'] = key_
            new_facet_dict['count'] = value_
            restructured_facets[key]['items'].append(new_facet_dict)
    search_results['search_facets'] = restructured_facets

    # check if some extension needs to modify the search results
    for item in plugins.PluginImplementations(plugins.IPackageController):
        search_results = item.after_search(search_results, data_dict)

    # After extensions have had a chance to modify the facets, sort them by
    # display name.
    for facet in search_results['search_facets']:
        search_results['search_facets'][facet]['items'] = sorted(
            search_results['search_facets'][facet]['items'],
            key=lambda facet: facet['display_name'], reverse=True)

    return search_results


def _get_capacity_fq(fq):
    capacity_fq = None
    if toolkit.get_endpoint() == ('dataset', 'search'):
        # The selected visibility from the form comes through in the fq query as a string
        # Strip and split to get the visibility value
        #  Not sure if this is risky using the fq and better to use the request.args to get value
        visibility = next((q.strip().split(":")[-1].strip('"') for q in fq.split() if 'visibility:' in q), 'all')
        # Store the selected visibility in a global variable so the value can be re-selected on the visibility dataset search template
        toolkit.g.visibility_selected = visibility
        if visibility in ['private', 'public']:
            capacity_fq = f"capacity:{visibility}"

        # Remove the `visibility` from the `fq` search param as we've now used it to
        fq = ' '.join(p for p in fq.split() if 'visibility:' not in p)

    return capacity_fq, fq
