from .._adapter import PackagedFixtureAdapter


def create_adapter(root, manifest):
    return PackagedFixtureAdapter(root, manifest)
