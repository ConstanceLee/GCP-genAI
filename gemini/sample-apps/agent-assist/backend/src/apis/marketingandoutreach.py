"""This is a python utility file."""

from datetime import datetime, timedelta
import json

from flask import jsonify, request


def getMarketingAndOutreachData() -> tuple[dict, int]:
    """
    This function gets the marketing and outreach data from a JSON
      file and returns it in a JSON format.

    Args:
        None

    Returns:
        JSON: A JSON object containing the marketing and outreach data.
    """
    file_path = "data/likes.json"
    with open(file_path) as json_file:
        data = json.load(json_file)

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    if start_date is None or end_date is None:
        start_date = datetime.now() - timedelta(days=90)
        start_date = start_date.strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")

    (
        websiteTraffic,
        likes,
        comments,
        shares,
        emailsent,
        openrate,
        topPerformaingPlatform,
        chartData,
    ) = getMetricsData(data, start_date, end_date)

    return (
        jsonify(
            {
                "websiteTraffic": websiteTraffic,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "emailsent": emailsent,
                "openrate": openrate,
                "topPerformaingPlatform": topPerformaingPlatform,
                "chartData": chartData,
            }
        ),
        200,
    )


def getMetricsData(
    data: list, start_date: str, end_date: str
) -> tuple[int, int, int, int, int, float, str, list]:
    """
    This function gets the metrics data from a list of dictionaries and returns it in a tuple.

    Args:
        data (list): A list of dictionaries containing the marketing and outreach data.
        start_date (str): The start date of the data to be retrieved.
        end_date (str): The end date of the data to be retrieved.

    Returns:
        tuple: A tuple containing the website traffic, likes, comments,
        shares, emails sent, open rate, top performing platform, and chart data.
    """
    websiteTraffic = 0
    likes = 0
    comments = 0
    shares = 0
    emailsent = 0
    mailopened = 0
    maxSales = 0
    topPerformaingPlatform = ""
    salesPltforms = [
        "facebook Sales",
        "newspaper Sales",
        "TVAds Sales",
        "insta Sales",
        "mail Sales",
        "telephone Sales",
    ]
    sumSales = {}
    for platform in salesPltforms:
        sumSales[platform] = 0
    for item in data:
        if (
            item["campaign_start_date"] >= start_date
            and item["campaign_start_date"] <= end_date
        ):
            websiteTraffic += item["websiteVisitors"]
            likes += item["instaLikes"] + item["facebookLikes"]
            comments += item["instaComments"] + item["facebookComments"]
            shares += item["facebookShares"]
            emailsent += item["numberOfMailSent"]
            mailopened += item["numberOfMailOpen"]
            for platform in salesPltforms:
                sumSales[platform] += item[platform.replace(" ", "")]

    for platform in salesPltforms:
        if sumSales[platform] > maxSales:
            maxSales = sumSales[platform]
            topPerformaingPlatform = platform

    openrate = 0.0
    if emailsent != 0:
        openrate = (mailopened * 100) / emailsent
    openrate = round(openrate, 2)

    chartData = []
    for platform in salesPltforms:
        chartData.append({"x": platform, "y1": sumSales[platform]})
    return (
        websiteTraffic,
        likes,
        comments,
        shares,
        emailsent,
        openrate,
        topPerformaingPlatform.split(" ")[0],
        chartData,
    )
