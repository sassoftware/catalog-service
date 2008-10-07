
class BaseDriver(object):
    def __init__(self, mintClient, cfg, nodeFactory):
        self._cfg = cfg
        self._mintClient = mintClient
        self._client = None
        self._nodeFactory = nodeFactory


    def _getUrlParams(self):
        return self._nodeFactory.urlParams

    def _setUrlParams(self, urlParams):
        self._nodeFactory.urlParams = urlParams

    urlParams = property(_getUrlParams, _setUrlParams)

    def isValidCloudName(self, cloudName):
        raise NotImplementedError
