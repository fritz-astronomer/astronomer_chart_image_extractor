"""extract_images.py - part of the airgap scripts
INPUTS
- astronomer chart, unzipped

OUTPUTS
- images.json, flat json depiction of ChartImage fields
- airgap_images.yaml, assembled nested yaml
"""
import collections.abc
import json
import os
from dataclasses import dataclass
from typing import List
from typing import Set

import jmespath as jmespath
import yaml
from dotenv import load_dotenv

load_dotenv()

DEFAULT_REPO_STRINGS = json.loads(os.getenv("DEFAULT_REPO_STRINGS", '["quay.io", "docker.io", "ghcr.io", "gcr.io"]'))
NEW_REPO_STRING = os.getenv("NEW_REPO_STRING")

# Include helm chart museum or nginx for hosting astronomer_certified.json
INCLUDE_CHART_MUSEUM = os.getenv("INCLUDE_CHART_MUSEUM", 'true') == "true"
INCLUDE_NGINX_ASTRONOMER_CERTIFIED = os.getenv("INCLUDE_NGINX_ASTRONOMER_CERTIFIED", 'true') == "true"
INCLUDE_PRIVATE_CA_ALPINE = os.getenv("INCLUDE_PRIVATE_CA_ALPINE", 'true') == "true"

SHOULD_EXTRACT_IMAGES = os.getenv("SHOULD_EXTRACT_IMAGES", 'true') == "true"
SHOULD_CREATE_AIRGAP_IMAGES_YAML = os.getenv("SHOULD_CREATE_AIRGAP_IMAGES_YAML", 'true') == "true"

ASTRONOMER_SUBCHARTS_PATH = os.getenv("ASTRONOMER_CHART_PATH", "astronomer/charts")
AIRFLOW_CHART_PATH = os.getenv("AIRFLOW_CHART_PATH", 'airflow')
IMAGES_JSON_PATH = os.getenv("IMAGES_JSON_PATH", 'images.json')
AIRGAP_IMAGES_YAML_PATH = os.getenv('AIRGAP_IMAGES_PATH', 'templates/airgap_images.yaml')


@dataclass(eq=True, unsafe_hash=True, order=True)
class ChartImage:
    original_image: str

    image: str  # just the image astronomer/ap-airflow, without repo or tag
    image_key: str = ""
    new_image_key: str = ""

    tag: str = ""
    tag_key: str = ""
    new_tag_key: str = ""

    repo: str = ""
    repo_key: str = ""
    new_repo_key: str = ""


# noinspection PyTypeChecker
def r_find_all(haystack: dict, needles: List[str], key=""):
    """In a dictionary, find all needles, returning any found keys as JMESPaths (path.to.json.key)
    >>> r_find_all({}, [""])  # find nothing in nothing
    []
    >>> r_find_all({"foo":"bar"}, ["bar"])  # find one at root
    ['foo']
    >>> r_find_all({"foo":{"b":"bar"}}, ["bar"])  # find one nested
    ['foo.b']
    >>> r_find_all({"foo":{"b":["bar"]}}, ["bar"])  # find one nested array
    ['foo.b']
    >>> r_find_all({"foo":{"b":["baz"]}}, ["bar"])  # find none nested
    []
    >>> r_find_all({"foo":{"b":["bar"], "c": "bar"}, "baz": {"boo": "bar"}, "bop": "bar"}, ["bar"])  # find many in many
    ['foo.b', 'foo.c', 'baz.boo', 'bop']
    >>> r_find_all({"foo":{"b":["baz"]}, 'c': 'bar'}, ["bar", 'baz'])  # find multi
    ['foo.b', 'c']
    """
    res = []
    for k, v in haystack.items():
        if isinstance(v, collections.abc.Mapping):  # descend if dict
            maybe_keys = r_find_all(v, needles, key + k + ".")
            if len(maybe_keys):
                res += maybe_keys
        elif type(v) in [str, list] and any([needle in v for needle in needles]):
            res.append(key + k)
    return res


def set_at_path(tree, path, value):
    """Recurse down a dictionary and create branches or set a leaf to value
    >>> set_at_path({}, "foo", "bar")  # set something simple
    {'foo': 'bar'}
    >>> set_at_path({}, "foo.bar", "baz")
    {'foo': {'bar': 'baz'}}
    >>> set_at_path({"foo": {"bop": "boo"}}, "foo.bar", "baz")
    {'foo': {'bop': 'boo', 'bar': 'baz'}}
    """

    if '.' in path:
        head, *tail = path.split('.')
        tree[head] = tree.get(head, {})
        if isinstance(tree[head], dict):
            set_at_path(tree[head], '.'.join(tail), value)
        else:
            print(f"{tree} - tree[{head}] is not a dict, path: {'.'.join(tail)}, value: {value}")
    else:
        tree[path] = value
    return tree


def replace_repo_string(new_repo_string, old_string, repo_strings):
    """
    >>> replace_repo_string("foo", "", [])
    ''
    >>> replace_repo_string("foo", "barbaz", [])
    'barbaz'
    >>> replace_repo_string("foo", "barbaz", ['bar'])
    'foobaz'
    >>> replace_repo_string("ecr.us-east-1.amazonaws.com/bla", "quay.io/my/image:tag1.2-3.4", ['ghcr.io', 'quay.io'])
    'ecr.us-east-1.amazonaws.com/bla/my/image:tag1.2-3.4'

    >>> replace_repo_string('ecr.aws.us-east-1.com:5000', 'bitnami/minideb', DEFAULT_REPO_STRINGS)
    'bitnami/minideb'
    """
    new_string = old_string
    for old_repo_string in repo_strings:
        if old_repo_string in old_string:
            new_string = old_string.replace(old_repo_string, new_repo_string)
    return new_string


# noinspection PyTypeChecker
def extract_images_from_subchart(subchart: str, chart_values: dict, repo_strings: List[str]) -> Set[ChartImage]:
    """Takes a subchart's values.yaml, as a dict, and recursively find any instances of `repo_strings` as key value
    :return Set[ChartImage] - assembled set of ChartImage info

    KEDA subchart features non-standard key names and <repo>/<image>/<tag> as values
    >>> values = {"keda": {"image": {"keda": "quay.io/astronomer/ap-keda:1.3.0", "metricsAdapter": "quay.io/astronomer/ap-keda-metrics-adapter:1.3.0"}}}
    >>> actual = sorted(list(extract_images_from_subchart('keda', values, repo_strings=['quay.io'])))
    >>> actual[0].repo, actual[0].image, actual[0].tag, actual[0].image_key, actual[0].tag_key, actual[0].repo_key
    ('quay.io', 'astronomer/ap-keda', '1.3.0', 'keda.image.keda', 'keda.image.keda', 'keda.image.keda')
    >>> actual[1].repo, actual[1].image, actual[1].tag, actual[1].image_key, actual[1].tag_key, actual[1].repo_key
    ('quay.io', 'astronomer/ap-keda-metrics-adapter', '1.3.0', 'keda.image.metricsAdapter', 'keda.image.metricsAdapter', 'keda.image.metricsAdapter')

    Postgresql subchart has separate "registry", "repository", and "tag" keys
    >>> values = {"image": {"registry": "docker.io", "repository": "bitnami/postgresql", "tag": "11.11.0-debian-10-r30"}}
    >>> actual = sorted(list(extract_images_from_subchart('postgresql', values, repo_strings=['quay.io', 'docker.io'])))
    >>> actual[0].repo, actual[0].image, actual[0].tag, actual[0].image_key, actual[0].tag_key, actual[0].repo_key
    ('docker.io', 'bitnami/postgresql', '11.11.0-debian-10-r30', 'image.repository', 'image.tag', 'image.registry')

    NGINX subchart has "repository" and "tag" keys with the registry embedded in the image
    >>> values = {"images": {"nginx": {"repository": "quay.io/astronomer/ap-nginx", "tag": "0.45.0"}, "defaultBackend": {"repository": "quay.io/astronomer/ap-default-backend", "tag": "0.25.1"}}}
    >>> actual = sorted(list(extract_images_from_subchart('nginx', values, ['quay.io'])))
    >>> actual[0].repo, actual[0].image, actual[0].tag, actual[0].image_key, actual[0].tag_key, actual[0].repo_key
    ('quay.io', 'astronomer/ap-default-backend', '0.25.1', 'images.defaultBackend.repository', 'images.defaultBackend.tag', 'images.defaultBackend.repository')
    >>> actual[1].repo, actual[1].image, actual[1].tag, actual[1].image_key, actual[1].tag_key, actual[1].repo_key
    ('quay.io', 'astronomer/ap-nginx', '0.45.0', 'images.nginx.repository', 'images.nginx.tag', 'images.nginx.repository')

    >>> values = {"defaultAirflowRepository":"quay.io/astronomer/ap-airflow","defaultAirflowTag":"2.0.0-buster","images":{"airflow":{"repository":"quay.io/astronomer/ap-airflow","tag":None},"statsd":{"repository":"quay.io/astronomer/ap-statsd-exporter","tag":"0.18.0"},"redis":{"repository":"quay.io/astronomer/ap-redis","tag":"6.2.1"},"pgbouncer":{"repository":"quay.io/astronomer/ap-pgbouncer","tag":"1.8.1"},"pgbouncerExporter":{"repository":"quay.io/astronomer/ap-pgbouncer-exporter","tag":"0.9.2"}}}
    >>> actual = sorted(list(extract_images_from_subchart("astronomer.houston.config.deployments.helm" , values, ['quay.io'])))
    >>> actual[0].repo, actual[0].image, actual[0].tag, actual[0].new_image_key, actual[0].new_tag_key, actual[0].new_repo_key
    ('quay.io', 'astronomer/ap-airflow', '2.0.0-buster', 'astronomer.houston.config.deployments.helm.defaultAirflowRepository', 'astronomer.houston.config.deployments.helm.defaultAirflowTag', '')
    >>> actual[1].repo, actual[1].image, actual[1].tag, actual[1].new_image_key, actual[1].new_tag_key, actual[1].new_repo_key
    ('quay.io', 'astronomer/ap-airflow', None, 'astronomer.houston.config.deployments.helm.images.airflow.repository', 'astronomer.houston.config.deployments.helm.images.airflow.tag', '')
    """
    images = set()
    for image_key in r_find_all(chart_values, repo_strings):
        # split the tail off of the rest of the path
        node_key, leaf_key = ".".join(image_key.split(".")[:-1]), image_key.split(".")[-1]
        if node_key:
            node_key_with_dot = node_key + '.'
        else:
            node_key_with_dot = ''

        # extract the parent node
        node = jmespath.search(node_key, chart_values) if node_key else chart_values
        # extract the image tag we got from the initial search
        found_image = node[leaf_key]

        # BASE CASE - just an "image" key, nothing else
        image = ChartImage(
            original_image=found_image,
            image=found_image,
            image_key=image_key,
            new_image_key=f"{subchart}.{node_key_with_dot + leaf_key}",
        )

        # REGISTRY CASE - some were {"registry": 'docker.io', "image": 'foo/bar'}, fix those
        if leaf_key == 'registry':
            image.repo = node['registry']
            image.repo_key = node_key_with_dot + 'registry'
            image.new_repo_key = f"{subchart}.{image.repo_key}"

            # IMAGE - need to fix if it was 'registry' which only contained 'docker.io'
            if 'image' in node or 'repository' in node:
                image.image = node['image' if 'image' in node else 'repository']
                if 'image' in node:
                    image.image_key = node_key_with_dot + 'image'
                else:
                    image.image_key = node_key_with_dot + 'repository'
                image.new_image_key = f'{subchart}.{image.image_key}'

        # TAG - either 'tag' key or in image key separated by
        if 'tag' in node or 'defaultAirflowTag' in node or ':' in found_image:
            if ':' in found_image:
                [_image, tag] = found_image.split(":")
                image.image = _image
                image.tag = tag
            else:
                image.tag = node['tag'] if 'tag' in node else node['defaultAirflowTag']
            if "tag" in node:
                image.tag_key = node_key_with_dot + 'tag'
            elif 'defaultAirflowTag' in node:
                image.tag_key = node_key_with_dot + 'defaultAirflowTag'
            else:
                image.tag_key = image.image_key
            image.new_tag_key = f"{subchart}.{image.tag_key}"

        # FIX IMAGE: Remove 'quay.io' or etc from image, add it to 'repo'
        for repo_string in repo_strings:
            if repo_string in image.image:
                image.original_image = image.image
                image.image = image.image.replace(repo_string + "/", "")
                image.repo = repo_string
                image.repo_key = image.image_key

        # Filter out false positive - one key randomly contained 'gcr.io' but no other worthwhile values
        if '/' in image.image:
            images.add(image)
    return images


def extract_images(repo_strings, astronomer_subcharts_path: str = ASTRONOMER_SUBCHARTS_PATH, airflow_chart_path: str = AIRFLOW_CHART_PATH) -> Set[ChartImage]:
    """Take the YAML block from the file and pull out image/tag/repo/registry and assemble them into ChartImage"""
    images = set()
    astronomer_subcharts = [(subchart, f"{astronomer_subcharts_path}/{subchart}/values.yaml") for subchart in os.listdir(astronomer_subcharts_path)]
    airflow_chart = [('astronomer.houston.config.deployments.helm', f'{airflow_chart_path}/values.yaml')]
    for subchart, values_filename in astronomer_subcharts + airflow_chart:
        # If values.yaml exists and is open-able, load it as yaml
        if not os.path.exists(values_filename):
            print(f"Missing file: {values_filename}, skipping!")
        else:
            with open(values_filename, 'r') as f:
                chart_values = yaml.safe_load(f)
                subchart_images = extract_images_from_subchart(subchart, chart_values, repo_strings)
                images = images | subchart_images  # set union, filter out any dupes
    return images


def chart_json_to_image(chart: dict, override_repo: str = None, with_tag: bool = True) -> str:
    if override_repo is not None:
        repo = override_repo+"/" if override_repo != "" else override_repo
    else:
        repo = chart['repo'] + '/'
    return f"{repo}{chart['image']}{':' + chart['tag'] if chart['tag'] and with_tag else ''}"


def main():
    if SHOULD_EXTRACT_IMAGES:
        print(f"Extracting images from subcharts at '{ASTRONOMER_SUBCHARTS_PATH}/*' to assemble '{IMAGES_JSON_PATH}' ...")
        with open(IMAGES_JSON_PATH, 'w') as f:
            images = extract_images(DEFAULT_REPO_STRINGS, ASTRONOMER_SUBCHARTS_PATH)
            if INCLUDE_CHART_MUSEUM:
                images.add(ChartImage(original_image="", image='helm/chartmuseum', repo="ghcr.io", tag="v0.13.1"))
            if INCLUDE_NGINX_ASTRONOMER_CERTIFIED:
                images.add(ChartImage(original_image="", image='nginx', repo="docker.io", tag="stable"))
            if INCLUDE_PRIVATE_CA_ALPINE:
                images.add(ChartImage(original_image="", image='alpine', repo="docker.io", tag="latest"))
            json.dump([image.__dict__ for image in images], f, indent=2)

    if SHOULD_CREATE_AIRGAP_IMAGES_YAML:
        print(f"Loading '{IMAGES_JSON_PATH}' to assemble '{AIRGAP_IMAGES_YAML_PATH}' ...")
        d = {}
        with open(IMAGES_JSON_PATH, 'r') as f:
            for image in json.loads(f.read()):
                if image['new_repo_key']:
                    replaced_repo_tag = replace_repo_string(NEW_REPO_STRING, image['repo'], DEFAULT_REPO_STRINGS)
                    set_at_path(d, image['new_repo_key'], replaced_repo_tag)
                if image['new_image_key']:
                    if image['repo_key'] != image['image_key']:  # repository key exists, we just want the image
                        image_value = chart_json_to_image(image, override_repo='', with_tag=False)
                    else:
                        image_value = chart_json_to_image(
                            image,
                            override_repo=NEW_REPO_STRING,
                            with_tag=image['tag_key'] == image['image_key']  # if image has tag in it, originally
                        )
                    set_at_path(d, image['new_image_key'], image_value)
                if image['new_tag_key'] != image['new_image_key']:
                    set_at_path(d, image['new_tag_key'], image['tag'])

        with open(AIRGAP_IMAGES_YAML_PATH, 'w') as f:
            f.write(yaml.safe_dump(d))


if __name__ == '__main__':
    main()
