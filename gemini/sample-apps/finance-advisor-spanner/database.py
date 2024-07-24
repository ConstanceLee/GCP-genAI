"""This file is for database operations done by the application """

import os
from google.cloud import spanner
from google.api_core.client_options import ClientOptions
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

instance_id = os.getenv("instance_id")
database_id = os.getenv("database_id")
api_endpoint = os.getenv("api_endpoint")

options = ClientOptions(api_endpoint=api_endpoint)
spanner_client = spanner.Client(client_options=options)
# if(api_endpoint !=''):
#     options = ClientOptions(api_endpoint=api_endpoint)
#     spanner_client = spanner.Client(client_options=options)
# else:
#     spanner_client = spanner.Client()

# Get a Cloud Spanner instance by ID.
instance = spanner_client.instance(instance_id)
# Get a Cloud Spanner database by ID.
database = instance.database(database_id)

def spanner_read_data(query):
    """This function helps read data from spanner"""
    with database.snapshot() as snapshot:
        results = snapshot.execute_sql(query)
        rows = list()
        for row in results:
            rows.append(row)
        # Get column names
        cols = [x.name for x in results.fields]
        # Convert to pandas dataframe
        result_df = pd.DataFrame(rows, columns=cols)
    return result_df


def spanner_read_data_list(query):
    """This function helps read data from spanner and returns data as a list"""
    with database.snapshot() as snapshot:
        results = snapshot.execute_sql(query)
        rows = list()
        for row in results:
            rows.append(row)
    return rows


def spanner_read_data_withparam(query, vector_input):
    """This function helps read data from spanner with input params"""
    with database.snapshot() as snapshot:

        results = snapshot.execute_sql(
            query,
            params={"vector": vector_input},
        )
        rows = list()
        for row in results:
            rows.append(row)
        # Get column names
        cols = [x.name for x in results.fields]
        # Convert to pandas dataframe
        result_df = pd.DataFrame(rows, columns=cols)

    return result_df


def fts_query(query_params):
    """This function runs Full Text Search Query"""
    print("Query Part", query_params)

    if query_params[1] == "":
        query = (
            "SELECT DISTINCT fund_name,investment_strategy,investment_managers,fund_trailing_return_ytd,top5_holdings FROM EU_MutualFunds WHERE SEARCH(investment_strategy_Tokens, '"
            + query_params[0]
            + "') order by fund_name;"
        )
    else:
        query = (
            "SELECT DISTINCT fund_name, manager, strategy, score FROM (SELECT fund_name , investment_managers AS manager, investment_strategy as strategy, SCORE_NGRAMS(investment_managers_Substring_Tokens_NGRAM, '"
            + query_params[1]
            + "') AS score FROM EU_MutualFunds WHERE SEARCH_NGRAMS(investment_managers_Substring_Tokens_NGRAM, '"
            + query_params[1]
            + "', min_ngrams=>1) AND SEARCH(investment_strategy_Tokens, '"
            + query_params[0]
            + "') ) ORDER BY score DESC;"
        )

    returnVals = dict()
    returnVals["query"] = query
    print("FTS Query", query)
    df = spanner_read_data(query)

    returnVals["data"] = df
    return returnVals


def semantic_query(query_params):
    """This function runs Semantic Text Search Query"""
    print("Query Part", query_params)
    if query_params[1].strip() != "":
        query = (
            "SELECT fund_name, investment_strategy,investment_managers, COSINE_DISTANCE( investment_strategy_Embedding, (SELECT embeddings. VALUES FROM ML.PREDICT( MODEL EmbeddingsModel, (SELECT '"
            + query_params[0]
            + "' AS content) ) ) ) AS distance FROM EU_MutualFunds WHERE investment_strategy_Embedding is not NULL  AND  search_substring(investment_managers_substring_tokens, '"
            + query_params[1]
            + "')ORDER BY distance LIMIT 10;"
        )
    else:
        query = (
            "SELECT fund_name, investment_strategy,investment_managers, COSINE_DISTANCE( investment_strategy_Embedding, (SELECT embeddings. VALUES FROM ML.PREDICT( MODEL EmbeddingsModel, (SELECT '"
            + query_params[0]
            + "' AS content) ) ) ) AS distance FROM EU_MutualFunds WHERE investment_strategy_Embedding is not NULL  ORDER BY distance LIMIT 10;"
        )
    returnVals = dict()
    returnVals["query"] = query
    print("Semantic Query", query)
    df = spanner_read_data(query)

    returnVals["data"] = df
    return returnVals


def semantic_query_ann(query_params):
    """This function runs Semantic Text Search ANN Query"""
    print("Query Part", query_params)

    query1 = (
        'SELECT embeddings. VALUES as vector FROM ML.PREDICT( MODEL EmbeddingsModel, (SELECT "'
        + query_params[0]
        + '" AS content) ) ;'
    )
    print(query1)
    vector_input = spanner_read_data_list(query1)
    # vector_input[0][0]

    if query_params[1].strip() != "":
        # query2="SELECT fund_name, investment_strategy,investment_managers, APPROX_EUCLIDEAN_DISTANCE( investment_strategy_Embedding_vector, @vector, options => JSON '{\"num_leaves_to_search\": 10}') AS distance FROM EU_MutualFunds @{force_index=InvestmentStrategyEmbeddingIndex} WHERE investment_strategy_Embedding_vector is not NULL ORDER BY distance LIMIT 10; "
        query2 = (
            "SELECT funds.fund_name, funds.investment_strategy, funds.investment_managers FROM (SELECT NewMFSequence, APPROX_EUCLIDEAN_DISTANCE(investment_strategy_Embedding_vector, @vector, options => JSON '{\"num_leaves_to_search\": 10}') AS distance FROM EU_MutualFunds @{force_index = InvestmentStrategyEmbeddingIndex} WHERE investment_strategy_Embedding_vector IS NOT NULL ORDER BY distance LIMIT 500 ) AS ann JOIN EU_MutualFunds AS funds ON ann.NewMFSequence = funds.NewMFSequence WHERE SEARCH_NGRAMS(funds.investment_managers_Substring_Tokens_NGRAM, '"
            + query_params[1]
            + "',min_ngrams=>1)  ORDER BY SCORE_NGRAMS(funds.investment_managers_Substring_Tokens_NGRAM, '"
            + query_params[1]
            + "') desc;"
        )
    else:
        query2 = "SELECT fund_name, investment_strategy, investment_managers, APPROX_EUCLIDEAN_DISTANCE(investment_strategy_Embedding_vector, @vector, options => JSON '{\"num_leaves_to_search\": 10}') AS distance FROM EU_MutualFunds @{force_index = InvestmentStrategyEmbeddingIndex} WHERE investment_strategy_Embedding_vector IS NOT NULL ORDER BY distance LIMIT 100;"
    print(query2)
    results_df = spanner_read_data_withparam(query2, vector_input[0][0])

    # if query_params[1].strip() != "":
    #     query = (
    #         "SELECT fund_name, investment_strategy,investment_managers, COSINE_DISTANCE( investment_strategy_Embedding, (SELECT embeddings. VALUES FROM ML.PREDICT( MODEL EmbeddingsModel, (SELECT '"
    #         + query_params[0]
    #         + "' AS content) ) ) ) AS distance FROM EU_MutualFunds WHERE investment_strategy_Embedding is not NULL  AND  search_substring(investment_managers_substring_tokens, '"
    #         + query_params[1]
    #         + "')ORDER BY distance LIMIT 10;"
    #     )
    # else:
    #     query = (
    #         "SELECT fund_name, investment_strategy,investment_managers, COSINE_DISTANCE( investment_strategy_Embedding, (SELECT embeddings. VALUES FROM ML.PREDICT( MODEL EmbeddingsModel, (SELECT '"
    #         + query_params[0]
    #         + "' AS content) ) ) ) AS distance FROM EU_MutualFunds WHERE investment_strategy_Embedding is not NULL  ORDER BY distance LIMIT 10;"
    #     )
    return_vals = dict()
    return_vals["query"] = query2
    #print("Semantic ANN Query", query2)
    # df = spanner_read_data(query)

    return_vals["data"] = results_df
    return return_vals


def like_query(query_params):
    """This function runs Precise Text Search Query"""

    if query_params[1] == "EXCLUDE":
        query_params[1] = "AND"
    query = (
        " SELECT DISTINCT fund_name, investment_managers, investment_strategy FROM EU_MutualFunds WHERE investment_managers LIKE ('%"
        + query_params[3]
        + "%') AND ( investment_strategy LIKE ('%"
        + query_params[0]
        + "%') "
        + query_params[1]
        + " investment_strategy LIKE ('%"
        + query_params[2]
        + "%') ) ORDER BY fund_name;"
    )
    print(query)

    # df = spanner_read_data(query)
    return_vals = dict()
    return_vals["query"] = query
    #print("FTS Query", query)
    df = spanner_read_data(query)

    return_vals["data"] = df
    return return_vals


def compliance_query(query_params):
    """This function runs Compliance Graph  Search Query"""
    query = (
        "GRAPH FundGraph MATCH (sector:Sector {sector_name: '"
        + query_params[0]
        + "'})<-[:BELONGS_TO]-(company:Company)<-[h:HOLDS]-(fund:Fund) RETURN fund.fund_name, SUM(h.percentage) AS totalHoldings GROUP BY fund.fund_name NEXT FILTER totalHoldings > "
        + query_params[1]
        + " RETURN fund_name, totalHoldings"
    )

    return_vals = dict()
    # print("Graph Query", query)
    return_vals["query"] = query
    df = spanner_read_data(query)
    return_vals["data"] = df
    return return_vals


def graph_dtls_query():
    """This function runs Graph Details  Query"""
    query = "select * from  Companies;"
    # df = spanner_read_data(query)

    return_vals = dict()
    df_companies = spanner_read_data(query)
    return_vals["Companies"] = df_companies

    query = "select * from  Sectors;"
    df_sectors = spanner_read_data(query)
    return_vals["Sectors"] = df_sectors

    query = "select * from  Managers LIMIT 100;"
    df_managers = spanner_read_data(query)
    return_vals["Managers"] = df_managers

    query = "SELECT * from CompanyBelongsSector;"
    df_comp_sec_edge = spanner_read_data(query)
    return_vals["CompanySectorRelation"] = df_comp_sec_edge

    query = " SELECT mgrs.NewMFSequence,fund_name,ManagerSeq from ManagerManagesFund mgrs JOIN EU_MutualFunds funds ON mgrs.NewMFSequence =  funds.NewMFSequence where ManagerSeq in (select ManagerSeq from Managers LIMIT 100);"
    mgr_fund_edge = spanner_read_data(query)
    return_vals["ManagerFundRelation"] = mgr_fund_edge

    query = "select fund_name, NewMFSequence from EU_MutualFunds where NewMFSequence in (SELECT NewMFSequence FROM FundHoldsCompany);"
    # query = "SELECT mgrs.NewMFSequence,fund_name,ManagerSeq from ManagerManagesFund mgrs JOIN EU_MutualFunds funds ON mgrs.NewMFSequence =  funds.NewMFSequence ;"
    # query = "select fund_name, NewMFSequence from EU_MutualFunds where NewMFSequence in (SELECT NewMFSequence FROM FundHoldsCompany);"

    funds_node = spanner_read_data(query)
    return_vals["Funds"] = funds_node

    query = "SELECT * FROM FundHoldsCompany;"
    funds_hold_company_edge = spanner_read_data(query)
    return_vals["FundsHoldsCompaniesRelation"] = funds_hold_company_edge

    return return_vals