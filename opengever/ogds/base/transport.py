from five import grok
from opengever.ogds.base.exceptions import TransportationError
from opengever.ogds.base.interfaces import IDataCollector
from opengever.ogds.base.interfaces import IObjectCreator
from opengever.ogds.base.interfaces import ITransporter
from opengever.ogds.base.utils import decode_for_json, encode_after_json
from opengever.ogds.base.utils import remote_json_request
from plone.dexterity.interfaces import IDexterityFTI, IDexterityContent
from plone.dexterity.utils import createContent, addContentToContainer
from plone.dexterity.utils import iterSchemata
from plone.namedfile.interfaces import INamedFileField
from z3c.relationfield.interfaces import IRelation, IRelationChoice
from z3c.relationfield.interfaces import IRelationList
from zope import schema
from zope.annotation.interfaces import IAnnotations
from zope.app.intid.interfaces import IIntIds
from zope.component import getAdapters, queryAdapter, getAdapter
from zope.component import getUtility
from zope.event import notify
from zope.interface import Interface
from zope.lifecycleevent import ObjectCreatedEvent
from zope.lifecycleevent import ObjectModifiedEvent
import DateTime
import base64
import json


BASEDATA_KEY = 'basedata'
REQUEST_KEY = 'object_data'

ORIGINAL_INTID_ANNOTATION_KEY = 'transporter_original-intid'


_marker = object()


class Transporter(grok.GlobalUtility):
    """ The transporter utility is able to copy objects to other
    clients.
    """

    grok.provides(ITransporter)

    def transport_to(self, obj, target_cid, container_path):
        """ Copies a *object* to another client (*target_cid*).
        """

        jsondata = json.dumps(self._extract_data(obj))

        request_data = {
            REQUEST_KEY: jsondata,
            }
        return remote_json_request(
            target_cid, '@@transporter-receive-object',
            path=container_path, data=request_data)

    def transport_from(self, container, source_cid, path):
        """ Copies the object under *path* from client with *source_cid* into
        the local folder *container*
        *path* is the relative path of the object to its plone site root.
        """

        data = remote_json_request(source_cid,
                                   '@@transporter-extract-object-json',
                                   path=path)
        data = encode_after_json(data)

        obj = self._create_object(container, data)
        return obj

    def receive(self, container, request):
        jsondata = request.get(REQUEST_KEY)
        data = json.loads(jsondata)
        data = encode_after_json(data)
        obj = self._create_object(container, data)
        return obj

    def extract(self, obj):
        """ Returns a JSON dump of *obj*
        """
        return json.dumps(self._extract_data(obj))

    def _extract_data(self, obj):
        """ Serializes a object
        """
        data = {}
        # base data
        creator = self._get_object_creator(obj.portal_type)
        data[BASEDATA_KEY] = creator.extract(obj)
        # collect data
        collectors = getAdapters((obj,), IDataCollector)
        for name, collector in collectors:
            data[name] = collector.extract()
        data = decode_for_json(data)

        return data

    def _create_object(self, container, data):
        """ Creates the object with the data
        """
        portal_type = data[BASEDATA_KEY]['portal_type']
        # base data
        creator = self._get_object_creator(portal_type)
        obj = creator.create(container, data[BASEDATA_KEY])
        # insert data from collectors
        collectors = getAdapters((obj,), IDataCollector)
        for name, collector in collectors:
            collector.insert(data[name])
        # let the object reindex by creating a modified event, which also
        # runs stuff like globalindex, if needed.
        notify(ObjectModifiedEvent(obj))
        return obj

    def _get_object_creator(self, portal_type):
        # get the FTI
        fti = getUtility(IDexterityFTI, name=portal_type)
        # do we have a specific one?
        creator = queryAdapter(fti, IObjectCreator, name=portal_type)
        if not creator:
            creator = getAdapter(fti, IObjectCreator, name='')
        return creator


class ReceiveObject(grok.View):
    """The `ReceiveObject` view receives a object-transporter request on the
    target client and creates or updates the object.
    """

    grok.name('transporter-receive-object')
    grok.require('cmf.AddPortalContent')
    grok.context(Interface)

    def render(self):
        transporter = getUtility(ITransporter)
        container = self.context
        obj = transporter.receive(container, self.request)
        portal = self.context.portal_url.getPortalObject()
        portal_path = '/'.join(portal.getPhysicalPath())

        intids = getUtility(IIntIds)

        data = {
            'path': '/'.join(obj.getPhysicalPath())[
                len(portal_path) + 1:],
            'intid': intids.queryId(self.context)
            }

        # Set correct content type for JSON response
        self.request.response.setHeader("Content-type", "application/json")

        return json.dumps(data)


class ExtractObject(grok.View):
    """The `ExtractObject` view is called by the transporter on a specific
    context on the source client for extract the data and returning it to
    the receiver.
    """

    grok.name('transporter-extract-object-json')
    grok.require('cmf.AddPortalContent')
    grok.context(Interface)

    def render(self):
        transporter = getUtility(ITransporter)

        # Set correct content type for JSON response
        self.request.response.setHeader("Content-type", "application/json")

        return transporter.extract(self.context)


class DexterityObjectCreator(grok.Adapter):
    """Default adapter for creating dexterity objects. This adapter is used
    by the transporter utility for creating a object.
    The `IObjectCreator` adapts the FTI. This makes it possible to also support
    other FTI types such as Archetypes.
    """

    grok.context(IDexterityFTI)
    grok.provides(IObjectCreator)
    grok.name('')

    def extract(self, obj):
        return {
            'id': obj.getId(),
            'title': obj.Title(),
            'portal_type': obj.portal_type,
            }

    def create(self, container, data):

        title = data['title']
        if not isinstance(title, unicode):
            title = title.decode('utf-8')

        obj = createContent(data['portal_type'],
                            id=title,
                            title=title)
        notify(ObjectCreatedEvent(obj))
        obj = addContentToContainer(container,
                                    obj,
                                    checkConstraints=True)
        return obj


class DexterityFieldDataCollector(grok.Adapter):
    """The `DexterityFieldDataCollector` is used for extracting field data from
    a dexterity object and for setting it later on the target.
    This adapter is used by the transporter utility.
    """
    grok.context(IDexterityContent)
    grok.provides(IDataCollector)
    grok.name('field-data')

    def extract(self):
        """Extracts the field data and returns a dict of all data.
        """
        data = {}
        for schemata in iterSchemata(self.context):
            subdata = {}
            repr = schemata(self.context)
            for name, field in schema.getFieldsInOrder(schemata):
                value = getattr(repr, name, _marker)
                if value == _marker:
                    value = getattr(self.context, name, None)
                value = self.pack(name, field, value)
                subdata[name] = value
            if schemata.getName() in data.keys():
                raise TransportationError((
                        'Duplacte behavior names are not supported',
                        schemata.getName()))
            data[schemata.getName()] = subdata
        return data

    def insert(self, data):
        """Inserts the field data on self.context
        """
        for schemata in iterSchemata(self.context):
            repr = schemata(self.context)
            subdata = data[schemata.getName()]
            for name, field in schema.getFieldsInOrder(schemata):
                value = subdata[name]
                value = self.unpack(name, field, value)
                if value != _marker:
                    setattr(repr, name, value)

    def pack(self, name, field, value):
        """Packs the field data and makes it ready for transportation with
        json, which does only support basic data types.
        """
        if self._provided_by_one_of(field, [
                schema.interfaces.IDate,
                schema.interfaces.ITime,
                schema.interfaces.IDatetime,
                ]):
            if value:
                return str(value)
        elif self._provided_by_one_of(field, [
                INamedFileField,
                ]):
            if value:
                return {
                    'filename': value.filename,
                    'data': base64.encodestring(value.data),
                    }

        elif self._provided_by_one_of(field, (
                IRelation,
                IRelationChoice,
                IRelationList,)):
            # Remove all relations since we cannot guarantee anyway the they
            # are on the target. Relations have to be rebuilt by to tool which
            # uses the transporter - if required.
            if self._provided_by_one_of(field, (IRelation, IRelationChoice)):
                return None
            elif self._provided_by_one_of(field, (IRelationList,)):
                return []

        return value

    def unpack(self, name, field, value):
        """Unpacks the value from the basic json types to the objects which
        are stored on the field later.
        """

        if self._provided_by_one_of(field, [
                schema.interfaces.IDate,
                schema.interfaces.ITime,
                schema.interfaces.IDatetime,
                ]):
            if value:
                return DateTime.DateTime(value).asdatetime()

        if self._provided_by_one_of(field, [INamedFileField]):
            if value and isinstance(value, dict):
                filename = value['filename']
                data = base64.decodestring(value['data'])
                return field._type(data=data, filename=filename)
        return value

    def _provided_by_one_of(self, obj, ifaces):
        """Checks if at least one interface of the list `ifaces` is provied
        by the `obj`.
        """

        for ifc in ifaces:
            if ifc.providedBy(obj):
                return True
        return False


class OriginalIntidDataCollector(grok.Adapter):
    """This data collector stores the intid of the originally extracted
    object in the annotations of the copy. This is very important for being
    able to map the intids and fix relations.
    """

    grok.context(IDexterityContent)
    grok.provides(IDataCollector)
    grok.name('intid-data')

    def extract(self):
        intids = getUtility(IIntIds)
        return intids.getId(self.context)

    def insert(self, data):
        IAnnotations(self.context)[ORIGINAL_INTID_ANNOTATION_KEY] = data


class DublinCoreMetaDataCollector(grok.Adapter):
    """This data collector stores the standard dublin core data of
    plone objects, like the creation date or the creator.
    """

    grok.context(IDexterityContent)
    grok.provides(IDataCollector)
    grok.name('dublin-core')

    def extract(self):
        return {
            'creator': self.context.Creator(),
            'created': str(self.context.created()),
            }

    def insert(self, data):

        self.context.setCreators(data.get('creator'))

        self.context.creation_date = DateTime.DateTime(
            data.get('created'))
