# Copyright 2023 Google LLC. This software is provided as-is, without warranty
# or representation for any use or purpose. Your use of it is subject to your
# agreement with Google.
"""Vector Search implementation of the vector store"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Iterable, List, Optional, Type

import requests
from requests import Response

import google.auth
import google.auth.transport.requests
from google.cloud import aiplatform, aiplatform_v1, storage
from google.cloud.aiplatform import MatchingEngineIndex, MatchingEngineIndexEndpoint
from google.oauth2 import service_account
from google.oauth2.service_account import Credentials
from langchain.docstore.document import Document
from langchain.embeddings import TensorflowHubEmbeddings
from langchain.embeddings.base import Embeddings
from langchain.vectorstores.base import VectorStore

logger = logging.getLogger()


class VectorSearch(VectorStore):
    """
    Vertex Matching Engine implementation of the vector store.

    While the embeddings are stored in the Matching Engine, the embedded
    documents will be stored in GCS.

    An existing Index and corresponding Endpoint are preconditions for
    using this module.

    See usage in docs/modules/indexes/vectorstores/examples/matchingengine.ipynb

    Note that this implementation is mostly meant for reading if you are
    planning to do a real time implementation. While reading is a real time
    operation, updating the index takes close to one hour.
    """

    def __init__(
        self,
        project_id: str,
        region: str,
        index: MatchingEngineIndex,
        endpoint: MatchingEngineIndexEndpoint,
        embedding: Embeddings,
        gcs_client: storage.Client,
        index_client: aiplatform_v1.IndexServiceClient,
        index_endpoint_client: aiplatform_v1.IndexEndpointServiceClient,
        gcs_bucket_name: str,
        credentials: Credentials = None,
    ):
        """Vertex Matching Engine implementation of the vector store.

        While the embeddings are stored in the Matching Engine, the embedded
        documents will be stored in GCS.

        An existing Index and corresponding Endpoint are preconditions for
        using this module.

        See usage in
        docs/modules/indexes/vectorstores/examples/matchingengine.ipynb.

        Note that this implementation is mostly meant for reading if you are
        planning to do a real time implementation. While reading is a real time
        operation, updating the index takes close to one hour.

        Attributes:
            project_id: The GCS project id.
            index: The created index class. See
            ~:func:`VectorSearch.from_components`.
            endpoint: The created endpoint class. See
            ~:func:`VectorSearch.from_components`.
            embedding: A :class:`Embeddings` that will be used for
            embedding the text sent. If none is sent, then the
            multilingual Tensorflow Universal Sentence Encoder will be used.
            gcs_client: The Google Cloud Storage client.
            credentials (Optional): Created GCP credentials.
        """
        super().__init__()

        self.project_id = project_id
        self.region = region
        self.index = index
        self.endpoint = endpoint
        self.embedding = embedding
        self.gcs_client = gcs_client
        self.index_client = index_client
        self.index_endpoint_client = index_endpoint_client
        self.gcs_client = gcs_client
        self.credentials = credentials
        self.gcs_bucket_name = gcs_bucket_name

    def add_texts(
        self, texts: Iterable[str], metadatas: Optional[List[dict]]
    ) -> List[str]:
        """Run more texts through the embeddings and add to the vectorstore.

        Args:
            texts: Iterable of strings to add to the vectorstore.
            metadatas: Optional list of metadatas associated with the texts.

        Returns:
            List of ids from adding the texts into the vectorstore.
        """
        logger.debug("Embedding documents.")
        embeddings = self.embedding.embed_documents(list(texts))
        insert_datapoints_payload = []
        ids = []

        if metadatas is None:
            metadatas = [{} for _ in range(len(texts))]  # Default empty metadata


        # Streaming index update
        for idx, (embedding, text, metadata) in enumerate(
            zip(embeddings, texts, metadatas)
        ):
            # id_ = uuid.uuid4()
            # id_ = str(metadata[1]['allow_list'])[2:-2]
            # +'_'+str(metadata[2]['allow_list'])[2:-2]\
            # +'_'+str(metadata[3]['allow_list'])[2:-2]
            # id_ = metadata[-1].get('unique_id')

            if isinstance(metadata, dict):
                id_ = str(
                    str(metadata[0].get("allow_list"))[2:-2].replace(" ", "")
                    + "_"
                    + str(metadata[1].get("allow_list"))[2:-2].replace(" ", "")
                    + "_"
                    + str(metadata[2].get("allow_list"))[2:-2].replace(" ", "")
                    + "_"
                    + str(metadata[3].get("allow_list"))[2:-2].replace(" ", "")
                )
                id_ = id_.replace("/", "")
            elif isinstance(metadata, list):
                id_ = str(
                    str(metadata[0]["allow_list"])[2:-2].replace(" ", "")
                    + "_"
                    + str(metadata[1]["allow_list"])[2:-2].replace(" ", "")
                    + "_"
                    + str(metadata[2]["allow_list"])[2:-2].replace(" ", "")
                    + "_"
                    + str(metadata[3]["allow_list"])[2:-2].replace(" ", "")
                )
                id_ = id_.replace("/", "")
            else:
                id_ = str(uuid.uuid4())
                print("matadata not a dictionary", type(metadata))

            ids.append(id_)
            self._upload_to_gcs(text, f"documents/{id_}")
            # metadatas[idx]
            insert_datapoints_payload.append(
                aiplatform_v1.IndexDatapoint(
                    datapoint_id=str(id_),
                    feature_vector=embedding,
                    restricts=metadata if metadata else [],
                )
            )
            if idx % 100 == 0:
                upsert_request = aiplatform_v1.UpsertDatapointsRequest(
                    index=self.index.name, datapoints=insert_datapoints_payload
                )
                _ = self.index_client.upsert_datapoints(
                    request=upsert_request
                )  # pylint: disable=W0612
                insert_datapoints_payload = []
        if len(insert_datapoints_payload) > 0:
            upsert_request = aiplatform_v1.UpsertDatapointsRequest(
                index=self.index.name, datapoints=insert_datapoints_payload
            )
            _ = self.index_client.upsert_datapoints(request=upsert_request)

        logger.debug("Updated index with new configuration.")
        logger.info("Indexed %s documents to Matching Engine.", len(ids))

        return ids

    def _upload_to_gcs(self, data: str, gcs_location: str) -> None:
        """Uploads data to gcs_location.

        Args:
            data: The data that will be stored.
            gcs_location: The location where the data will be stored.
        """
        bucket = self.gcs_client.get_bucket(self.gcs_bucket_name)
        blob = bucket.blob(gcs_location)
        blob.upload_from_string(data)

    def get_matches(
        self,
        embeddings: List[str],
        n_matches: int,
        index_endpoint: MatchingEngineIndexEndpoint,
    ) -> Response:
        """
        get matches from matching engine given a vector query
        Uses public endpoint

        """

        request_data = {
            "deployed_index_id": index_endpoint.deployed_indexes[0].id,
            "return_full_datapoint": True,
            "queries": [
                {
                    "datapoint": {"datapoint_id": f"{i}", "feature_vector": emb},
                    "neighbor_count": n_matches,
                }
                for i, emb in enumerate(embeddings)
            ],
        }

        endpoint_address = self.endpoint.public_endpoint_domain_name
        rpc_address = f"https://{endpoint_address}/v1beta1/{index_endpoint.resource_name}:findNeighbors"  # pylint: disable=line-too-long
        endpoint_json_data = json.dumps(request_data)

        logger.debug("Querying Matching Engine Index Endpoint %s", rpc_address)

        request = google.auth.transport.requests.Request()
        self.credentials.refresh(request)
        header = {"Authorization": "Bearer " + self.credentials.token}

        return requests.post(
            rpc_address, data=endpoint_json_data, headers=header, timeout=60
        )

    def _get_index_id(self) -> str:
        """Gets the correct index id for the endpoint.

        Returns:
            The index id if found (which should be found) or throws
            ValueError otherwise.
        """
        for index in self.endpoint.deployed_indexes:
            if index.index == self.index.name:
                return index.id

        raise ValueError(
            f"No index with id {self.index.name} "
            f"deployed on enpoint "
            f"{self.endpoint.display_name}."
        )

    def _download_from_gcs(self, gcs_location: str) -> str:
        """Downloads from GCS in text format.

        Args:
            gcs_location: The location where the file is located.

        Returns:
            The string contents of the file.
        """
        bucket = self.gcs_client.get_bucket(self.gcs_bucket_name)
        try:
            blob = bucket.blob(gcs_location)
            return blob.download_as_string()
        except Exception:  # pylint: disable=W0718,W0703
            return ""

    @classmethod
    def from_texts(
        cls: Type["VectorSearch"],
        texts: List[str],
        embedding: Embeddings,
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> "VectorSearch":
        """Use from components instead."""
        raise NotImplementedError(
            "This method is not implemented. Instead, \
                you should initialize the class"
            " with `VectorSearch.from_components(...)` and then call "
            "`from_texts`"
        )

    @classmethod
    def from_documents(
        cls: Type["VectorSearch"],
        documents: List[str],
        embedding: Embeddings,
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> "VectorSearch":
        """Use from components instead."""
        raise NotImplementedError(
            "This method is not implemented. Instead, \
                you should initialize the class"
            " with `VectorSearch.from_components(...)` and then call "
            "`from_documents`"
        )

    @classmethod
    def from_components(
        cls: Type["VectorSearch"],
        project_id: str,
        region: str,
        gcs_bucket_name: str,
        index_id: str,
        endpoint_id: str,
        credentials_path: Optional[str] = None,
        embedding: Optional[Embeddings] = None,
    ) -> "VectorSearch":
        """Takes the object creation out of the constructor.

        Args:
            project_id: The GCP project id.
            region: The default location making the API calls. It must have
            the same location as the GCS bucket and must be regional.
            gcs_bucket_name: The location where the vectors will be stored in
            order for the index to be created.
            index_id: The id of the created index.
            endpoint_id: The id of the created endpoint.
            credentials_path: (Optional) The path of the Google credentials on
            the local file system.
            embedding: The :class:`Embeddings` that will be used for
            embedding the texts.

        Returns:
            A configured VectorSearch with the texts added to the index.
        """

        gcs_bucket_name = cls._validate_gcs_bucket(gcs_bucket_name)

        # Set credentials
        if credentials_path:
            credentials = cls._create_credentials_from_file(credentials_path)
        else:
            credentials, _ = google.auth.default()
            request = google.auth.transport.requests.Request()
            credentials.refresh(request)

        index = cls._create_index_by_id(index_id, region, credentials)
        endpoint = cls._create_endpoint_by_id(
            endpoint_id, project_id, region, credentials
        )

        gcs_client = cls._get_gcs_client(credentials, project_id)
        index_client = cls._get_index_client(region, credentials)
        index_endpoint_client = cls._get_index_endpoint_client(region, credentials)
        cls._init_aiplatform(project_id, region, gcs_bucket_name, credentials)

        return cls(
            project_id=project_id,
            region=region,
            index=index,
            endpoint=endpoint,
            embedding=embedding or cls._get_default_embeddings(),
            gcs_client=gcs_client,
            index_client=index_client,
            index_endpoint_client=index_endpoint_client,
            credentials=credentials,
            gcs_bucket_name=gcs_bucket_name,
        )

    @classmethod
    def _validate_gcs_bucket(cls, gcs_bucket_name: str) -> str:
        """Validates the gcs_bucket_name as a bucket name.

        Args:
              gcs_bucket_name: The received bucket uri.

        Returns:
              A valid gcs_bucket_name or throws ValueError if full path is
              provided.
        """
        gcs_bucket_name = gcs_bucket_name.replace("gs://", "")
        if "/" in gcs_bucket_name:
            raise ValueError(
                f"The argument gcs_bucket_name should only be "
                f"the bucket name. Received {gcs_bucket_name}"
            )
        return gcs_bucket_name

    @classmethod
    def _create_credentials_from_file(
        cls, json_credentials_path: Optional[str]
    ) -> Optional[Credentials]:
        """Creates credentials for GCP.

        Args:
             json_credentials_path: The path on the file system where the
             credentials are stored.

         Returns:
             An optional of Credentials or None, in which case the default
             will be used.
        """

        credentials = None
        if json_credentials_path is not None:
            credentials = service_account.Credentials.from_service_account_file(
                json_credentials_path
            )

        return credentials

    @classmethod
    def _create_index_by_id(
        cls, index_id: str, region: str, credentials: "Credentials"
    ) -> MatchingEngineIndex:
        """Creates a MatchingEngineIndex object by id.

        Args:
            index_id: The created index id.

        Returns:
            A configured MatchingEngineIndex.
        """

        logger.debug("Creating matching engine index with id %s", index_id)
        index_client = cls._get_index_client(region, credentials)
        request = aiplatform_v1.GetIndexRequest(name=index_id)
        return index_client.get_index(request=request)

    @classmethod
    def _create_endpoint_by_id(
        cls, endpoint_id: str, project_id: str, region: str, credentials: "Credentials"
    ) -> MatchingEngineIndexEndpoint:
        """Creates a MatchingEngineIndexEndpoint object by id.

        Args:
            endpoint_id: The created endpoint id.

        Returns:
            A configured MatchingEngineIndexEndpoint.
            :param project_id:
            :param region:
            :param credentials:
        """

        logger.debug("Creating endpoint with id %s", endpoint_id)
        return aiplatform.MatchingEngineIndexEndpoint(
            index_endpoint_name=endpoint_id,
            project=project_id,
            location=region,
            credentials=credentials,
        )

    @classmethod
    def _get_gcs_client(
        cls, credentials: "Credentials", project_id: str
    ) -> "storage.Client":
        """Lazily creates a GCS client.

        Returns:
            A configured GCS client.
        """

        return storage.Client(credentials=credentials, project=project_id)

    @classmethod
    def _get_index_client(
        cls, region: str, credentials: "Credentials"
    ) -> "storage.Client":
        """Lazily creates a Matching Engine Index client.

        Returns:
            A configured Matching Engine Index client.
        """
        endpoint = f"{region}-aiplatform.googleapis.com"
        return aiplatform_v1.IndexServiceClient(
            client_options={"api_endpoint": endpoint}, credentials=credentials
        )

    @classmethod
    def _get_index_endpoint_client(
        cls, region: str, credentials: "Credentials"
    ) -> "storage.Client":
        """Lazily creates a Matching Engine Index Endpoint client.

        Returns:
            A configured Matching Engine Index Endpoint client.
        """
        endpoint = f"{region}-aiplatform.googleapis.com"
        return aiplatform_v1.IndexEndpointServiceClient(
            client_options={"api_endpoint": endpoint}, credentials=credentials
        )

    @classmethod
    def _init_aiplatform(
        cls,
        project_id: str,
        region: str,
        gcs_bucket_name: str,
        credentials: "Credentials",
    ) -> None:
        """Configures the aiplatform library.

        Args:
            project_id: The GCP project id.
            region: The default location making the API calls. It must have
            the same location as the GCS bucket and must be regional.
            gcs_bucket_name: GCS staging location.
            credentials: The GCS Credentials object.
        """

        logger.debug(
            "Initializing AI Platform for project %s on %s and for %s.",
            project_id,
            region,
            gcs_bucket_name,
        )
        aiplatform.init(
            project=project_id,
            location=region,
            staging_bucket=gcs_bucket_name,
            credentials=credentials,
        )

    @classmethod
    def _get_default_embeddings(cls) -> TensorflowHubEmbeddings:
        """This function returns the default embedding."""
        return TensorflowHubEmbeddings()
