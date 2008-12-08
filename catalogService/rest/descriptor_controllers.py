
from catalogService.rest.base_cloud import BaseCloudController
from catalogService.rest.response import XmlResponse

class CredentialsDescriptorController(BaseCloudController):
    def index(self, request):
        return XmlResponse(self.driver.getCredentialsDescriptor())

class ConfigurationDescriptorController(BaseCloudController):
    def index(self, request):
        return XmlResponse(self.driver(request).getCloudConfigurationDescriptor())

class DescriptorController(BaseCloudController):
    urls = dict(
        credentials = CredentialsDescriptorController,
        configuration = ConfigurationDescriptorController,
    )
