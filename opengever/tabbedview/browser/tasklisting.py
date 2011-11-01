from five import grok
from ftw.journal.interfaces import IJournalizable
from ftw.table.interfaces import ITableSource, ITableSourceConfig
from opengever.base.browser.helper import client_title_helper
from opengever.globalindex.model.task import Task
from opengever.globalindex.utils import indexed_task_link_helper
from opengever.tabbedview import _
from opengever.tabbedview.browser.listing import ListingView
from opengever.tabbedview.browser.tabs import OpengeverTab
from opengever.tabbedview.helper import overdue_date_helper
from opengever.tabbedview.helper import readable_date
from opengever.tabbedview.helper import readable_date_set_invisibles
from opengever.tabbedview.helper import readable_ogds_author
from opengever.tabbedview.helper import task_id_checkbox_helper
from opengever.tabbedview.helper import workflow_state
from opengever.task.helper import task_type_helper
from zope.app.pagetemplate import ViewPageTemplateFile
from zope.interface import implements, Interface
from opengever.tabbedview.browser.sqltablelisting import SqlTableSource


class IGlobalTaskTableSourceConfig(ITableSourceConfig):
    """Marker interface for table source configurations using the
    `opengever.globalindex` as source.
    """


class GlobalTaskListingTab(grok.View, OpengeverTab,
                           ListingView):
    """A tabbed view mixing which brings support for listing tasks from
    the SQL (globally over all clients).

    There is support for searching, batching and ordering.
    """

    implements(IGlobalTaskTableSourceConfig)

    grok.context(IJournalizable)
    grok.require('zope2.View')

    sort_on = 'modified'
    sort_reverse = False
    #lazy must be false otherwise there will be no correct batching
    lazy = False

    # the model attributes is used for a dynamic textfiltering functionality
    model = Task
    enabled_actions = [
        'reset_tableconfiguration',
        ]
    major_actions = []

    select_all_template = ViewPageTemplateFile('select_all_globaltasks.pt')
    selection = ViewPageTemplateFile("selection_tasks.pt")

    columns = (

        ('', task_id_checkbox_helper),

        {'column': 'review_state',
         'column_title': _(u'column_review_state', default=u'Review state'),
         'transform': workflow_state},

        {'column': 'title',
         'column_title': _(u'column_title', default=u'Title'),
         'transform': indexed_task_link_helper},

        {'column': 'task_type',
         'column_title': _(u'column_task_type', default=u'Task type'),
         'transform': task_type_helper},

        {'column': 'deadline',
         'column_title': _(u'column_deadline', default=u'Deadline'),
         'transform': overdue_date_helper},

        {'column': 'completed',
         'column_title': _(u'column_date_of_completion',
                           default=u'Date of completion'),
         'transform': readable_date_set_invisibles},

        {'column': 'responsible',
         'column_title': _(u'label_responsible_task', default=u'Responsible'),
         'transform': readable_ogds_author},

        {'column': 'issuer',
         'column_title': _(u'label_issuer', default=u'Issuer'),
         'transform': readable_ogds_author},

        {'column': 'created',
         'column_title': _(u'column_issued_at', default=u'Issued at'),
         'transform': readable_date},

        {'column': 'client_id',
         'column_title': _('column_client', default=u'Client'),
         'transform': client_title_helper},

        {'column': 'sequence_number',
         'column_title': _(u'column_sequence_number',
                           default=u'Sequence number')},

        )

    __call__ = ListingView.__call__
    update = ListingView.update
    render = __call__


class GlobalTaskTableSource(SqlTableSource):
    """Source adapter for Tasks we got from SQL
    """

    grok.implements(ITableSource)
    grok.adapts(IGlobalTaskTableSourceConfig, Interface)

    def build_query(self):
        """Builds the query based on `get_base_query()` method of config.
        Returns the query object.
        """

        # initalize config
        self.config.update_config()

        # get the base query from the config
        query = self.config.get_base_query()
        query = self.validate_base_query(query)

        # ordering
        query = self.extend_query_with_ordering(query)

        # filter
        if self.config.filter_text:
            query = self.extend_query_with_textfilter(
                query, self.config.filter_text)

        # reviewstate-filter
        review_state_filter = self.request.get('review_state', None)

        if review_state_filter == 'false':
            review_state_filter = False
        else:
            review_state_filter = True

        query = self.extend_query_with_statefilter(query, review_state_filter)

        # batching
        if self.config.batching_enabled and not self.config.lazy:
            query = self.extend_query_with_batching(query)

        return query

    def extend_query_with_statefilter(self, query, open_state):
        """When a state filter is active, we add a filter which select just the open tasks"""

        open_task_states = [
            'task-state-cancelled',
            'task-state-open',
            'task-state-in-progress',
            'task-state-resolved',
            'task-state-rejected',
            'forwarding-state-open',
        ]

        if open_state:
            query = query.filter(Task.review_state.in_(open_task_states))

        return query