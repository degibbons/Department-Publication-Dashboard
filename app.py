## Department Publication Dashboard

# Run with 'shiny run --reload --launch-browser ./app.py' in Terminal when in the directory

import re
import os
import csv
import datetime
import calendar
import statistics
import numpy as np
from shiny import reactive, req
from shiny.express import input, render, ui
from shiny.types import FileInfo
from shinywidgets import render_plotly
import pandas as pd
import plotly.express as px

year_designations = {
    # Each Year Designation is [Start Month, Start Day],[End Month, End Day]
    "Calendar_Year": [[1, 1], [12, 31]],
    "Academic_Year": [[8, 1], [7, 31]],
    "Fiscal_Year": [[7, 1], [6, 30]],
}

publish_data_dict: dict = {}

PERCENT_SUPER_HEADER = "Research %, Based on fall semester (e.g. 2003/2004 academic year is considered 2003)"

df_data_styles = [
    {
        "cols": [0, 1, 2],
        "style": {"width": "150px"},
    },
    {
        "cols": [3],
        "style": {"width": "300px"},
    },
    {
        "cols": [4],
        "style": {"width": "450px"},
    },
]


def read_in_file_all_data():
    """Read in the raw publication data that includes all the publications"""
    req(input.file1())
    file: list[FileInfo] | None = input.file1()
    if file is not None:
        all_raw_data = pd.read_excel(
            file[0]["datapath"], sheet_name="All Data", index_col=None
        )
        return all_raw_data


def read_in_file_publisher_data():
    """Read in the raw publisher data detailing names and research percentages"""
    req(input.file1())
    file: list[FileInfo] | None = input.file1()
    if file is not None:
        publisher_raw_data = pd.read_excel(
            file[0]["datapath"], sheet_name="Publishers", index_col=None, header=[0, 1]
        )
        return publisher_raw_data


def check_publisher_repeats(publisher_names_full):
    """Check for publisher name repeats and assign numbers to names if
    a name appears more than once"""
    publisher_list = []
    for each_name in publisher_names_full:
        publisher_list.append(each_name[1])
    name_counts = []
    for each_name in publisher_list:
        if publisher_list.count(each_name) > 1:
            if each_name not in name_counts:
                name_counts.append(each_name)
    if len(name_counts) > 0:
        for each_repeat_name in name_counts:
            repeat_count = 1
            for index, each_name in enumerate(publisher_list):
                if publisher_list[index] == each_repeat_name:
                    publisher_list[index] = each_name + "_" + str(repeat_count)
                    repeat_count += 1
    return publisher_list, name_counts


@render.ui
@reactive.event(input.file1, ignore_none=True)
def create_publisher_data():
    """Create a dictionary with all publishers and their corresponding publications and other assigned information"""
    all_raw_data = read_in_file_all_data()
    publisher_raw_data = read_in_file_publisher_data()
    publisher_names_full = create_publisher_tuplelist(publisher_raw_data)
    if all_raw_data is not None:
        if publisher_raw_data is not None:
            all_data = all_raw_data.drop(
                ["Online published", "Number of NYIT \nStudent Authors"], axis=1
            )
            publisher_data = publisher_raw_data.sort_index(axis=1).drop(
                [
                    PERCENT_SUPER_HEADER,
                    "Position",
                ],
                axis=1,
            )
            publisher_list, name_counts = check_publisher_repeats(publisher_names_full)

            for index, each_publisher in enumerate(publisher_list):
                # Use Default Dictionary Values to replace this
                publish_data_dict[each_publisher] = {
                    "Search_Name_Last": publisher_names_full[index][
                        1
                    ],  # Publisher Last Name - String
                    "Search_Name_First": publisher_names_full[index][
                        0
                    ],  # Publisher First Name - String
                    "Search_Name_Middle_I": None,  # Publisher Middle Initial - String
                    "Display_Name": publisher_names_full[index][1]
                    + ", "
                    + publisher_names_full[index][0],  # Whole Display Name - String
                    "Author_Publications": (),  # All Publications attributed to Publisher - Tuple of Tuples that include Date,DOI, & Citation((date,doi,citation),())
                    "Publication_Amount": 0,  # Amount of Publications attributed to Publisher - Integer
                    "Currently_at_NYIT": False,  # Still at NYIT or Not - Boolean
                    "Research_Percents": {},  # Percentage of Work as Research - Dictionary {Fall Semester Year:Percent - Float,}
                }
                if publish_data_dict[each_publisher]["Search_Name_Last"] in name_counts:
                    # Look for last name & First Initial
                    # If First Initial is the same, look for first name
                    # If first name is the same, look for middle initial if it exists
                    pass
                else:
                    regex_name_search_cite = (
                        r"(\W|\A)"
                        + publish_data_dict[each_publisher]["Search_Name_Last"]
                        + r"(\W)+"
                        + publish_data_dict[each_publisher]["Search_Name_First"][0]
                    )
                    regex_name_search_last = (
                        r"(\W|\A)"
                        + publish_data_dict[each_publisher]["Search_Name_Last"]
                        + r"(\W|\Z)"
                    )
                    name_match_cite = re.compile(regex_name_search_cite, re.IGNORECASE)
                    name_match_last = re.compile(regex_name_search_last, re.IGNORECASE)
                    all_attributed_publications = []
                    for index, row in all_data.iterrows():
                        publication_placeholder = []
                        if re.search(name_match_cite, row["Citation"]) is not None:
                            publication_placeholder.append(row["Print Published"])
                            publication_placeholder.append(row["DOI"])
                            publication_placeholder.append(row["Citation"])
                        if publication_placeholder:
                            all_attributed_publications.append(
                                tuple(publication_placeholder)
                            )
                    all_attributed_publications = tuple(all_attributed_publications)
                    publish_data_dict[each_publisher][
                        "Author_Publications"
                    ] = all_attributed_publications
                    publish_data_dict[each_publisher]["Publication_Amount"] = len(
                        all_attributed_publications
                    )
                    for index, row in publisher_data.iterrows():
                        if (
                            re.search(name_match_last, row["Last Name"].tolist()[0])
                            is not None
                        ):
                            publish_data_dict[each_publisher]["Currently_at_NYIT"] = (
                                row["Currently at NYIT"].tolist()[0]
                            )

            newest_publication_date = get_time_extremes("Newest")

            recorded_year_range = range(
                min(list(publisher_raw_data[PERCENT_SUPER_HEADER].columns)),
                newest_publication_date.year + 1,
            )

            for index, each_publisher in enumerate(publisher_list):
                year_dict = {}
                name_match = re.compile(
                    publish_data_dict[each_publisher]["Search_Name_Last"], re.IGNORECASE
                )
                for index, row in publisher_raw_data.iterrows():
                    if re.search(name_match, row["Last Name"].tolist()[0]) is not None:
                        for each_year in recorded_year_range:
                            research_percent = publisher_raw_data[
                                PERCENT_SUPER_HEADER, each_year
                            ].iloc[index]
                            if np.isnan(research_percent.item()):
                                year_dict[each_year] = 0
                            else:
                                year_dict[each_year] = research_percent.item()

                publish_data_dict[each_publisher]["Research_Percents"] = year_dict


def create_publisher_tuplelist(publisher_raw_data, first_last=True):
    """Create a tuple with each publisher name as ('first name','last name') or ('last name','first name')"""
    if first_last is True:
        publisher_names_full = tuple(
            zip(
                list(publisher_raw_data[publisher_raw_data.columns[0]]),
                list(publisher_raw_data[publisher_raw_data.columns[1]]),
            )
        )
    elif first_last is False:
        publisher_names_full = tuple(
            zip(
                list(publisher_raw_data[publisher_raw_data.columns[1]]),
                list(publisher_raw_data[publisher_raw_data.columns[0]]),
            )
        )
    else:
        raise ValueError("Not a valid option. Need true or false for first_last")
    return publisher_names_full


def convert_tuples_to_name_list(tuplelist):
    """Returns a list with each entry in ["last name, first name"] format"""
    author_list = []
    for each_name_combo in tuplelist:
        author_list.append(each_name_combo[0] + ", " + each_name_combo[1])
    return author_list


@render.ui
@reactive.event(input.file1, ignore_none=True)
def change_author():
    """Update the checklist to display all publisher names when raw data file is loaded in"""
    publisher_raw_data = read_in_file_publisher_data()
    publisher_names_full = create_publisher_tuplelist(
        publisher_raw_data, first_last=False
    )
    author_list = convert_tuples_to_name_list(publisher_names_full)
    ui.update_checkbox_group("selectauthor", choices=sorted(author_list))


def get_time_extremes(extreme_select, selected_publishers=None):
    """Get the upper or lower time extremes of the data in question, either globally or for selected publishers"""
    if selected_publishers is None:
        extreme_value = publish_data_dict[list(publish_data_dict.keys())[0]][
            "Author_Publications"
        ][0][0]
        for each_publisher_data in publish_data_dict.values():
            for each_publication in each_publisher_data["Author_Publications"]:
                if extreme_select == "Newest":
                    if each_publication[0] > extreme_value:
                        extreme_value = each_publication[0]
                elif extreme_select == "Oldest":
                    if each_publication[0] < extreme_value:
                        extreme_value = each_publication[0]
                else:
                    raise ValueError(
                        "Not a valid extreme option. Need 'Newest' or 'Oldest'"
                    )
    else:
        first_publisher = selected_publishers[0]
        extreme_value = publish_data_dict[first_publisher]["Author_Publications"][0][0]
        for each_publisher in selected_publishers:
            for each_publication in publish_data_dict[each_publisher][
                "Author_Publications"
            ]:
                if extreme_select == "Newest":
                    if each_publication[0] > extreme_value:
                        extreme_value = each_publication[0]
                elif extreme_select == "Oldest":
                    if each_publication[0] < extreme_value:
                        extreme_value = each_publication[0]
                else:
                    raise ValueError(
                        "Not a valid extreme option. Need 'Newest' or 'Oldest'"
                    )
    return extreme_value


def get_selecteddate_timeextremes(extreme_select):
    """Get the upper and lower bounds of the selected timespan"""
    if extreme_select == "Newest":
        selected_end_time = input.daterange()[1]
        dt_value = datetime.datetime.strptime(str(selected_end_time), "%Y-%m-%d")
    elif extreme_select == "Oldest":
        selected_start_time = input.daterange()[0]
        dt_value = datetime.datetime.strptime(str(selected_start_time), "%Y-%m-%d")
    else:
        raise ValueError("Not a valid extreme option. Need 'Newest' or 'Oldest'")
    return dt_value


def get_selected_timespan_months_list():
    """Get a list of the start dates of each month in the selected timespan"""
    selected_start_time = get_selecteddate_timeextremes("Oldest")
    selected_end_time = get_selecteddate_timeextremes("Newest")
    return pd.date_range(selected_start_time, selected_end_time, freq="MS").tolist()


def get_selected_timespan_year_bins():
    """Get a list of start and end dates for filtering out publications"""
    selected_start_time = get_selecteddate_timeextremes("Oldest")
    selected_end_time = get_selecteddate_timeextremes("Newest")
    start_date_dti = pd.DatetimeIndex([selected_start_time]).to_list()[0]
    end_date_dti = pd.DatetimeIndex([selected_end_time]).to_list()[0]
    if str(input.radio()) == "1":
        # Calendar Year
        x_axis_dates = pd.date_range(
            selected_start_time, selected_end_time, freq="YS-JAN"
        ).tolist()
    elif str(input.radio()) == "2":
        # Academic Year
        x_axis_dates = pd.date_range(
            selected_start_time, selected_end_time, freq="YS-AUG"
        ).tolist()
    elif str(input.radio()) == "3":
        # Fiscal Year
        x_axis_dates = pd.date_range(
            selected_start_time, selected_end_time, freq="YS-JUL"
        ).to_list()
    else:
        raise ValueError("Not a valid year designation option")
    if x_axis_dates[0] > start_date_dti:
        x_axis_dates.insert(0, start_date_dti)
    elif x_axis_dates[0] < start_date_dti:
        x_axis_dates[0] = start_date_dti
    if x_axis_dates[-1] < end_date_dti:
        x_axis_dates.append(end_date_dti)
    elif x_axis_dates[-1] > end_date_dti:
        x_axis_dates[-1] = end_date_dti
    return x_axis_dates


@render.ui
@reactive.event(input.alltime, ignore_none=True)
def change_timespan_all():
    """Change selected timepsan so the entire timespan includes all publications that have been recorded"""
    req(input.file1())
    newest_global_dt = get_time_extremes("Newest")
    oldest_global_dt = get_time_extremes("Oldest")
    ui.update_date_range("daterange", start=oldest_global_dt, end=newest_global_dt)


@reactive.effect
# @reactive.event(input.groupselector, ignore_none=True)
def change_selected_authors():
    """Change selected publishers so the only selected ones are still employed at NYIT"""
    req(input.file1())
    author_list = []
    if str(input.groupselector()) == "('Still at NYIT',)":
        for author_data in publish_data_dict.values():
            if author_data["Currently_at_NYIT"] is True:
                author_list.append(author_data["Display_Name"])

    elif str(input.groupselector()) == "('All',)":
        for author_data in publish_data_dict.values():
            author_list.append(author_data["Display_Name"])
    ui.update_checkbox_group("selectauthor", selected=author_list)


def get_selected_publishers(lname=True, allnames=False):
    """Get a list with the names of all the selected publishers"""
    if allnames is False:
        selected_names = input.selectauthor()
    else:
        publisher_raw_data = read_in_file_publisher_data()
        selected_names_temp = create_publisher_tuplelist(
            publisher_raw_data, first_last=False
        )
        selected_names = convert_tuples_to_name_list(selected_names_temp)
    if lname is True:
        selected_names_list = [each_name.split(",")[0] for each_name in selected_names]
    else:
        selected_names_list = selected_names
    return selected_names_list


def calculate_time_relevant_data(dates_only=True):
    """Get relevant data list corresponding to the selected publishers in the selected timespan"""
    selected_names = get_selected_publishers(lname=True, allnames=False)
    dt_start = get_selecteddate_timeextremes("Oldest")
    dt_end = get_selecteddate_timeextremes("Newest")
    total_publication_list = []
    total_publication_list_datesonly = []
    for each_selected_publisher in selected_names:
        total_publication_list = total_publication_list + list(
            publish_data_dict[each_selected_publisher]["Author_Publications"]
        )
    total_publication_list = sorted(total_publication_list, key=lambda x: x[0])
    # Filter out publications not in selected time range
    eliminate_list = []
    for each_pub in total_publication_list:
        if (each_pub[0] < dt_start) or (each_pub[0] > dt_end):
            eliminate_list.append(each_pub)
    for each_val in eliminate_list:
        while each_val in total_publication_list:
            total_publication_list.remove(each_val)
    for each_pub in total_publication_list:
        total_publication_list_datesonly.append(each_pub[0])
    if dates_only:
        return total_publication_list_datesonly
    else:
        return total_publication_list


def determine_pubcounts():
    """Generate publication lists corresponding to publishers, months, and the sums of each months"""
    dt_end = get_selecteddate_timeextremes("Newest")
    dt_month_end = datetime.datetime(
        dt_end.year, dt_end.month, calendar.monthrange(dt_end.year, dt_end.month)[1]
    )
    x_axis_dates = get_selected_timespan_months_list()
    total_publication_list = calculate_time_relevant_data(dates_only=False)
    month_publication_counts = [0] * len(x_axis_dates)
    for month_index, _ in enumerate(x_axis_dates):
        for each_pub in total_publication_list:
            if month_index == len(x_axis_dates) - 1:
                if (
                    each_pub[0] >= x_axis_dates[month_index]
                    and each_pub[0] <= dt_month_end
                ):
                    month_publication_counts[month_index] = (
                        month_publication_counts[month_index] + 1
                    )
            else:
                if (
                    each_pub[0] >= x_axis_dates[month_index]
                    and each_pub[0] < x_axis_dates[month_index + 1]
                ):
                    month_publication_counts[month_index] = (
                        month_publication_counts[month_index] + 1
                    )
    total_pubs_per_month = {
        "Months": x_axis_dates,
        "Pub_Counts": month_publication_counts,
    }
    return total_pubs_per_month


def determine_pubs_per_publisher():
    """Determine the amount of publications by publisher in the selected timespan"""
    selected_names = get_selected_publishers(lname=True, allnames=False)
    total_publication_list = calculate_time_relevant_data(dates_only=False)
    pub_counts_per_publisher = {}
    for each_name in selected_names:
        pub_counts_per_publisher[each_name] = 0
        name_match = re.compile(each_name, re.IGNORECASE)
        for each_filtered_pub in total_publication_list:
            if re.search(name_match, each_filtered_pub[2]) is not None:
                pub_counts_per_publisher[each_name] += 1
    return pub_counts_per_publisher


def determine_pubs_per_publisher_overtime(all_or_not=False):
    """Assembles a dictionary where the keys are each publisher and the values are a list of the dates of their publications in the selected timespan"""
    selected_names = get_selected_publishers(lname=True, allnames=all_or_not)
    total_publication_list = calculate_time_relevant_data(dates_only=False)
    pub_counts_per_publisher_over_time = {}
    for each_name in selected_names:
        pub_counts_per_publisher_over_time[each_name] = []
        name_match = re.compile(each_name, re.IGNORECASE)
        for each_filtered_pub in total_publication_list:
            if re.search(name_match, each_filtered_pub[2]) is not None:
                pub_counts_per_publisher_over_time[each_name].append(
                    each_filtered_pub[0]
                )
    return pub_counts_per_publisher_over_time


def determine_count_sums():
    """Determine the amount of publications by publisher in the selected timespan, but broken down by month"""
    selected_names = get_selected_publishers(lname=True, allnames=False)
    x_axis_dates = get_selected_timespan_months_list()
    dt_end = get_selecteddate_timeextremes("Newest")
    dt_month_end = datetime.datetime(
        dt_end.year, dt_end.month, calendar.monthrange(dt_end.year, dt_end.month)[1]
    )
    total_publication_list = calculate_time_relevant_data(dates_only=False)
    pub_counts_sums = {}
    month_publication_counts = [0] * len(x_axis_dates)
    for each_name in selected_names:
        pub_counts_sums[each_name] = month_publication_counts.copy()
    for month_index, _ in enumerate(x_axis_dates):
        for each_pub in total_publication_list:
            if month_index == len(x_axis_dates) - 1:
                if (
                    each_pub[0] >= x_axis_dates[month_index]
                    and each_pub[0] <= dt_month_end
                ):
                    month_publication_counts[month_index] = (
                        month_publication_counts[month_index] + 1
                    )
                    for each_publisher in selected_names:
                        name_match = re.compile(each_publisher, re.IGNORECASE)
                        if re.search(name_match, each_pub[2]) is not None:
                            pub_counts_sums[each_publisher][month_index] += 1
            else:
                if (
                    each_pub[0] >= x_axis_dates[month_index]
                    and each_pub[0] < x_axis_dates[month_index + 1]
                ):
                    month_publication_counts[month_index] = (
                        month_publication_counts[month_index] + 1
                    )
                    for each_publisher in selected_names:
                        name_match = re.compile(each_publisher, re.IGNORECASE)
                        if re.search(name_match, each_pub[2]) is not None:
                            pub_counts_sums[each_publisher][month_index] += 1
    return pub_counts_sums


def determine_pubs_per_range(
    date_year_ranges, selected_names, pub_counts_per_publisher_over_time
):
    """"""
    pubs_per_range = {}
    for range_index, each_range in enumerate(date_year_ranges):
        if each_range != date_year_ranges[-1]:
            pubs_per_range[
                str(date_year_ranges[range_index].year)
                + " - "
                + str(date_year_ranges[range_index + 1].year)
            ] = 0
            for each_selected_publisher in selected_names:
                for (
                    each_selected_publisher_publication
                ) in pub_counts_per_publisher_over_time[each_selected_publisher]:
                    if (
                        each_selected_publisher_publication
                        >= date_year_ranges[range_index]
                        and each_selected_publisher_publication
                        < date_year_ranges[range_index + 1]
                    ):
                        pubs_per_range[
                            str(date_year_ranges[range_index].year)
                            + " - "
                            + str(date_year_ranges[range_index + 1].year)
                        ] += 1
    return pubs_per_range


def determine_pubs_per_faculty_range(
    date_year_ranges, selected_names, pub_counts_per_publisher_over_time
):
    """"""
    pubs_per_faculty_in_range = {}
    each_faculty_pubs_in_range = {}
    for range_index, each_range in enumerate(date_year_ranges):
        if each_range != date_year_ranges[-1]:
            pubs_per_faculty_in_range[
                str(date_year_ranges[range_index].year)
                + " - "
                + str(date_year_ranges[range_index + 1].year)
            ] = {}
            for each_selected_publisher in selected_names:
                each_faculty_pubs_in_range[each_selected_publisher] = 0
                if len(pub_counts_per_publisher_over_time[each_selected_publisher]) > 0:
                    for (
                        each_selected_publisher_publication
                    ) in pub_counts_per_publisher_over_time[each_selected_publisher]:
                        if (
                            each_selected_publisher_publication
                            >= date_year_ranges[range_index]
                            and each_selected_publisher_publication
                            < date_year_ranges[range_index + 1]
                        ):
                            each_faculty_pubs_in_range[each_selected_publisher] += 1
            pubs_per_faculty_in_range[
                str(date_year_ranges[range_index].year)
                + " - "
                + str(date_year_ranges[range_index + 1].year)
            ] = each_faculty_pubs_in_range.copy()
    return pubs_per_faculty_in_range


def determine_each_faculty_pub_in_range(
    date_year_ranges, selected_names, pub_counts_per_publisher_over_time
):
    """"""
    each_faculty_pubs_in_range = {}
    for range_index, each_range in enumerate(date_year_ranges):
        if each_range != date_year_ranges[-1]:
            for each_selected_publisher in selected_names:
                each_faculty_pubs_in_range[each_selected_publisher] = 0
                for (
                    each_selected_publisher_publication
                ) in pub_counts_per_publisher_over_time[each_selected_publisher]:
                    if (
                        each_selected_publisher_publication
                        >= date_year_ranges[range_index]
                        and each_selected_publisher_publication
                        < date_year_ranges[range_index + 1]
                    ):
                        each_faculty_pubs_in_range[each_selected_publisher] += 1
    return each_faculty_pubs_in_range


def determine_facultypubs_dicts(pubs_per_faculty_in_range, selected_names):
    """Determine the amount of publications by faculty in the determined timespans"""
    faculty_pubs_by_faculty = {}
    for each_selected_publisher in selected_names:
        faculty_pubs_by_faculty[each_selected_publisher] = []
        for each_range in pubs_per_faculty_in_range.keys():
            faculty_pubs_by_faculty[each_selected_publisher].append(
                pubs_per_faculty_in_range[each_range][each_selected_publisher]
            )
    return faculty_pubs_by_faculty


def determine_faculty_pubs_percents(pubs_per_faculty_in_range, selected_names):
    """"""
    pubs_per_faculty_percent = {}

    for each_selected_publisher in selected_names:
        pubs_per_faculty_percent[each_selected_publisher] = []
        for (
            each_range,
            faculty_nums,
        ) in pubs_per_faculty_in_range.items():
            if (
                int(each_range[0:4])
                in publish_data_dict[each_selected_publisher]["Research_Percents"]
            ):
                if (
                    publish_data_dict[each_selected_publisher]["Research_Percents"][
                        int(each_range[0:4])
                    ]
                    != 0
                ):
                    pubs_per_faculty_percent[each_selected_publisher].append(
                        faculty_nums[each_selected_publisher]
                        / publish_data_dict[each_selected_publisher][
                            "Research_Percents"
                        ][int(each_range[0:4])]
                    )
                else:
                    pubs_per_faculty_percent[each_selected_publisher].append(0)
            else:
                pubs_per_faculty_percent[each_selected_publisher].append(0)
    return pubs_per_faculty_percent


def determine_med_max_min(med_max_min):
    """Determine the median, maximum, or minimum of the publications of the selected publishers over the selected timespan"""
    all_names = get_selected_publishers(lname=True, allnames=True)
    # print(all_names)
    selected_names = get_selected_publishers(lname=True, allnames=False)
    if len(selected_names) <= 0:
        return
    date_year_ranges = get_selected_timespan_year_bins()
    pub_counts_per_publisher_over_time = determine_pubs_per_publisher_overtime(
        all_or_not=True
    )
    pubs_per_faculty_in_range = determine_pubs_per_faculty_range(
        date_year_ranges,
        all_names,
        pub_counts_per_publisher_over_time,
    )
    pubs_per_faculty_percent = determine_faculty_pubs_percents(
        pubs_per_faculty_in_range, all_names
    )
    for each_selected_publisher in all_names:
        if all(v == 0 for v in pubs_per_faculty_percent[each_selected_publisher]):
            del pubs_per_faculty_percent[each_selected_publisher]
    med_max_min_values = {}
    if med_max_min not in ["Median", "Maximum", "Minimum"]:
        raise ValueError(
            "Not a valid med_max_min option. Need 'Median', 'Maximum', or 'Minimum'"
        )

    elif med_max_min == "Median":
        med_max_min_values["Median"] = []

        for each_efficiency_index in range(
            len(pubs_per_faculty_percent[selected_names[0]])
        ):
            temp_list = []
            for each_publisher_efficiency_num in pubs_per_faculty_percent.values():
                temp_list.append(each_publisher_efficiency_num[each_efficiency_index])
            temp_list = [i for i in temp_list if i != 0]
            if not temp_list:
                temp_list = [0]
            med_max_min_values["Median"].append(statistics.median(temp_list))

    elif med_max_min == "Maximum":
        med_max_min_values["Maximum"] = []

        for each_efficiency_index in range(
            len(pubs_per_faculty_percent[selected_names[0]])
        ):
            temp_list = []
            for each_publisher_efficiency_num in pubs_per_faculty_percent.values():
                temp_list.append(each_publisher_efficiency_num[each_efficiency_index])
            med_max_min_values["Maximum"].append(max(temp_list))
    return med_max_min_values


def determine_activity_stats(most_or_least, year_or_month):
    """Determine the most or least active month or year of the selected publishers"""
    if year_or_month not in ["Year", "Month"]:
        raise ValueError("Not a valid year_or_month option. Need 'Year' or 'Month'")
    if most_or_least not in ["Most", "Least"]:
        raise ValueError("Not a valid most_or_least option. Need 'Most' or 'Least'")
    selected_names = get_selected_publishers(lname=False, allnames=False)
    if year_or_month == "Year":
        if most_or_least == "Most":
            # Determine the most active year
            return
        elif most_or_least == "Least":
            # Determine the least active year
            return
    elif year_or_month == "Month":
        if most_or_least == "Most":
            # Determine the most active month
            return
        elif most_or_least == "Least":
            # Determine the least active month
            return


def write_csv_export():
    export_data = []
    dt_start = get_selecteddate_timeextremes("Oldest")
    dt_end = get_selecteddate_timeextremes("Newest")
    selected_names = get_selected_publishers(lname=True, allnames=False)
    for each_selected_author in selected_names:
        for each_publication in publish_data_dict[each_selected_author][
            "Author_Publications"
        ]:
            if (each_publication[0] >= dt_start) or (each_publication[0] <= dt_end):
                temp_dict = {
                    "Author": publish_data_dict[each_selected_author]["Display_Name"],
                    "Print Date Published": each_publication[0],
                    "DOI": each_publication[1],
                    "Citation": each_publication[2],
                }
                export_data.append(temp_dict)
    with open(
        str(input.csv_export_name()) + ".csv" if not None else "output.csv",
        "w",
        newline="",
        encoding="utf-8",
    ) as csvfile:
        fieldnames = [
            "Author",
            "Print Date Published",
            "DOI",
            "Citation",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(export_data)


################################## GUI CODE #################################
ui.page_opts(title="Anatomy Department Publication Dashboard", fillable=True)

with ui.sidebar(open="desktop", width=300):
    ui.input_checkbox("alltime", "All Recorded Time", False)
    ui.input_date_range("daterange", "Date Range", start="2000-01-01")
    ui.input_checkbox_group(
        "groupselector",
        "Group Selection",
        ["All", "Still at NYIT"],
        selected=[],
        inline=True,
    )
    ui.input_checkbox_group(
        "selectauthor",
        "Author Selector",
        [""],
        selected=[],
        inline=True,
    )

ui.input_file(
    "file1", "Upload Master File", accept=[".xlsx"], multiple=False, width="100%"
)

with ui.accordion(open=False):
    with ui.accordion_panel("Download Selected Data"):
        ui.markdown(
            "Download a .csv file including only the selected Authors in the selected Date Range."
        )
        ui.input_text(
            id="csv_export_name", label="Enter .csv export file name here", value=""
        )

        @render.download(label="Download .CSV")
        def download1():
            """
            Download export file using this function
            """
            ### Makes two copies instead of one
            #### one in designated location
            #### other is home directory
            path = os.path.join(
                os.path.dirname(__file__),
                (
                    str(input.csv_export_name()) + ".csv"
                    if input.csv_export_name() is not None
                    else "output.csv"
                ),
            )
            write_csv_export()
            return path


with ui.navset_pill(id="tab"):
    with ui.nav_panel("Dashboard"):
        with ui.layout_columns(fill=False):
            with ui.card():

                @render.ui
                @reactive.event(input.file1, ignore_none=True)
                def display_top_publishers():
                    """Display the top 5 publishers ranked by amount of publications recorded"""
                    publications_counts = {}
                    for each_faculty, faculty_data in publish_data_dict.items():
                        publications_counts[each_faculty] = faculty_data[
                            "Publication_Amount"
                        ]
                    sorted_items = sorted(
                        publications_counts.items(),
                        key=lambda item: item[1],
                        reverse=True,
                    )
                    ranked_list = [
                        (rank + 1, key, value)
                        for rank, (key, value) in enumerate(sorted_items)
                    ]
                    publisher_one = publish_data_dict[ranked_list[0][1]]["Display_Name"]
                    publisher_two = publish_data_dict[ranked_list[1][1]]["Display_Name"]
                    publisher_three = publish_data_dict[ranked_list[2][1]][
                        "Display_Name"
                    ]
                    publisher_four = publish_data_dict[ranked_list[3][1]][
                        "Display_Name"
                    ]
                    publisher_five = publish_data_dict[ranked_list[4][1]][
                        "Display_Name"
                    ]
                    publications_one = ranked_list[0][2]
                    publications_two = ranked_list[1][2]
                    publications_three = ranked_list[2][2]
                    publications_four = ranked_list[3][2]
                    publications_five = ranked_list[4][2]

                    top_5_string = f"""
                    ### **Top 5 Publishers**  
                    #### Rank
                    **1 -** {publisher_one} : {publications_one}  
                    **2 -** {publisher_two} : {publications_two}  
                    **3 -** {publisher_three} : {publications_three}  
                    **4 -** {publisher_four} : {publications_four}  
                    **5 -** {publisher_five} : {publications_five} 
                    """
                    return ui.markdown(top_5_string)

            with ui.card():

                @render.ui
                @reactive.event(input.file1, ignore_none=True)
                def display_publisher_stats():
                    # publish_data_dict = create_publisher_data()
                    selected_names = get_selected_publishers(True)
                    num_of_pubs = 0
                    # for each_name in selected_names:
                    #     num_of_pubs = num_of_pubs + publish_data_dict[each_name]["Publication_Amount"]

                    # Return counts per month

                    # Return counts per year

                    # time_span = 0
                    # most_active_month = "None"
                    # most_active_year = "None"
                    # most_active_month_average = "None"
                    # least_active_month = "None"
                    # least_active_year = "None"
                    # least_active_month_average = "None"
                    # stats_string = f"""
                    #     ### **Publication Stats of Selected Publishers**
                    #     **Number of Publications:** {num_of_pubs}
                    #     **Time Span Active:** {time_span}
                    #     **Most Active Month:** {most_active_month}
                    #     **Most Active Year:** {most_active_year}
                    #     **Most Active Average Month:** {most_active_month_average}
                    #     **Least Active Month:** {least_active_month}
                    #     **Least Active Year:** {least_active_year}
                    #     **Most Active Average Month:** {least_active_month_average}
                    #     """
                    stats_string = """
                    ### **Publication Stats of Selected Publishers**
                    Under Construction...
                    """
                    return ui.markdown(stats_string)

        with ui.layout_columns(col_widths=[6, 6, 6, 6, 12]):
            with ui.card(full_screen=True):
                ui.card_header("Total Over Selected Timespan")
                with ui.navset_card_tab(id="tab3"):
                    with ui.nav_panel("Total Over Time"):

                        @render_plotly
                        @reactive.event(input.selectauthor, ignore_none=True)
                        def total_over_timespan():
                            """Plot the total amount of publications published from the
                            selected publishers over the selected timespan"""
                            req(input.file1())
                            total_pubs_per_month = determine_pubcounts()
                            running_count = 0
                            for time_index in range(
                                len(total_pubs_per_month["Pub_Counts"])
                            ):
                                total_pubs_per_month["Pub_Counts"][
                                    time_index
                                ] += running_count
                                running_count = total_pubs_per_month["Pub_Counts"][
                                    time_index
                                ]

                            graph_data = {
                                "Months": total_pubs_per_month["Months"],
                                "Publication Counts": total_pubs_per_month[
                                    "Pub_Counts"
                                ],
                            }
                            graph_df = pd.DataFrame(graph_data)
                            fig = px.area(graph_df, x="Months", y="Publication Counts")
                            return fig

                    with ui.nav_panel("Author Contribution Over Time"):

                        @render_plotly
                        @reactive.event(input.selectauthor, ignore_none=True)
                        def total_over_timespan_perfaculty():
                            """Plot the total amount of publications published from the
                            selected publishers over the selected timespan, displaying the
                            individual contributions of each publisher stacked"""
                            req(input.file1())
                            pub_counts_sums = determine_count_sums()
                            dt_start = get_selecteddate_timeextremes("Oldest")
                            dt_end = get_selecteddate_timeextremes("Newest")
                            x_axis_dates = pd.date_range(
                                dt_start, dt_end, freq="MS"
                            ).tolist()
                            dt_months = x_axis_dates
                            for each_publisher_sums in pub_counts_sums.values():
                                running_count = 0
                                for time_index in enumerate(each_publisher_sums):
                                    each_publisher_sums[time_index[0]] += running_count
                                    running_count = each_publisher_sums[time_index[0]]

                            pub_month_list = []
                            publisher_list = []
                            pub_count_list = []
                            for index, each_publisher in enumerate(
                                list(pub_counts_sums.keys())
                            ):
                                temp_publisher_list = [each_publisher] * len(
                                    list(pub_counts_sums.values())[0]
                                )
                                publisher_list = publisher_list + temp_publisher_list
                                temp_pubcount_list = list(pub_counts_sums.values())[
                                    index
                                ]
                                pub_count_list = pub_count_list + temp_pubcount_list
                                temp_pubmonth_list = dt_months
                                pub_month_list = pub_month_list + temp_pubmonth_list

                            graph_data = {
                                "Months": pub_month_list,
                                "Publication Counts": pub_count_list,
                                "Publisher": publisher_list,
                            }

                            graph_df = pd.DataFrame(graph_data)
                            fig = px.area(
                                graph_df,
                                x="Months",
                                y="Publication Counts",
                                color="Publisher",
                            )
                            return fig

            with ui.card(full_screen=True):
                with ui.card_header("Proportional Breakdown"):

                    @render_plotly
                    @reactive.event(input.selectauthor, ignore_none=True)
                    def proportional_breakdown():
                        """Plot the percentage proportional breakdown of the total amount of
                        publications published from the selected publishers over the selected timespan
                        """
                        req(input.file1())
                        labels = []
                        sizes = []
                        pub_counts_per_publisher = determine_pubs_per_publisher()
                        for each_name, each_count in pub_counts_per_publisher.items():
                            labels.append(each_name)
                            sizes.append(each_count)

                        graph_data = {"Publisher": labels, "Publications": sizes}
                        graph_df = pd.DataFrame(graph_data)
                        fig = px.pie(
                            graph_df,
                            values="Publications",
                            names="Publisher",
                        )
                        return fig

            with ui.card(full_screen=True):
                with ui.card_header("Publication Frequency"):

                    @render_plotly
                    @reactive.event(input.selectauthor, ignore_none=True)
                    def publication_frequency():
                        """Plot the frequency of publications published from the
                        selected publishers over the selected timespan"""
                        req(input.file1())
                        total_publication_list_datesonly = calculate_time_relevant_data(
                            dates_only=True
                        )
                        x_axis_dates = get_selected_timespan_months_list()

                        for list_index, each_month in enumerate(
                            total_publication_list_datesonly
                        ):
                            total_publication_list_datesonly[list_index] = (
                                each_month.strftime("%Y-%m")
                            )

                        graph_df = pd.DataFrame(
                            {"Months": total_publication_list_datesonly}
                        )
                        fig = px.histogram(
                            graph_df,
                            x="Months",
                            nbins=len(x_axis_dates),
                            labels={"Months": "Month"},
                        )
                        return fig

            with ui.card(full_screen=True):
                with ui.card_header(
                    class_="d-flex justify-content-between align-items-center"
                ):
                    "Publications Per Year"
                ui.input_radio_buttons(
                    "radio",
                    "",
                    {
                        "1": "Calendar Year (January 1st - December 31st)",
                        "2": "Academic Year (August 1st - July 31st)",
                        "3": "Fiscal Year (July 1st - June 30th)",
                    },
                    inline=True,
                )

                with ui.navset_card_tab(id="tab2"):

                    with ui.nav_panel("Publication/Year"):

                        @render_plotly
                        def plot_pub_per_year():
                            """plot each timespan's amount of publications"""
                            req(input.file1())
                            selected_names = get_selected_publishers(
                                lname=True, allnames=False
                            )
                            date_year_ranges = get_selected_timespan_year_bins()

                            pub_counts_per_publisher_over_time = (
                                determine_pubs_per_publisher_overtime()
                            )

                            pubs_per_range = determine_pubs_per_range(
                                date_year_ranges,
                                selected_names,
                                pub_counts_per_publisher_over_time,
                            )

                            years_list = list(pubs_per_range.keys())
                            counts_list = list(pubs_per_range.values())
                            graph_df = pd.DataFrame(
                                {"Year": years_list, "Count": counts_list}
                            )

                            fig = px.bar(graph_df, x="Year", y="Count")
                            fig.update_xaxes(tickangle=90)
                            return fig

                    with ui.nav_panel("Publication/Faculty"):

                        @render_plotly
                        def plot_pubs_per_faculty():
                            """plot each timespan's amount of publications broken up by selected faculty"""
                            req(input.file1())
                            selected_names = get_selected_publishers(
                                lname=True, allnames=False
                            )
                            date_year_ranges = get_selected_timespan_year_bins()

                            pubs_per_publisher_over_time = (
                                determine_pubs_per_publisher_overtime()
                            )
                            pubs_per_faculty_in_range = (
                                determine_pubs_per_faculty_range(
                                    date_year_ranges,
                                    selected_names,
                                    pubs_per_publisher_over_time,
                                )
                            )

                            publishers_list = []
                            year_count_list = []
                            year_span_list = []

                            for (
                                each_timespan,
                                counts_broken_down,
                            ) in pubs_per_faculty_in_range.items():
                                for each_publisher in counts_broken_down.keys():
                                    publishers_list.append(each_publisher)
                                    year_count_list.append(
                                        counts_broken_down[each_publisher]
                                    )
                                    year_span_list.append(each_timespan)

                            graph_df = pd.DataFrame(
                                {
                                    "Year": year_span_list,
                                    "Count": year_count_list,
                                    "Publisher": publishers_list,
                                }
                            )

                            fig = px.bar(
                                graph_df, x="Year", y="Count", color="Publisher"
                            )
                            fig.update_xaxes(tickangle=90)
                            return fig

                    with ui.nav_panel("Potential Productivity"):

                        @render_plotly
                        def plot_faculty_productivity_stacked():
                            """Plot the efficiency of selected publishers in combination to display entire department productivity"""
                            req(input.file1())
                            selected_names = get_selected_publishers(True)
                            date_year_ranges = get_selected_timespan_year_bins()
                            pub_counts_per_publisher_over_time = (
                                determine_pubs_per_publisher_overtime()
                            )

                            pubs_per_faculty_in_range = (
                                determine_pubs_per_faculty_range(
                                    date_year_ranges,
                                    selected_names,
                                    pub_counts_per_publisher_over_time,
                                )
                            )
                            pubs_per_faculty_percent = determine_faculty_pubs_percents(
                                pubs_per_faculty_in_range, selected_names
                            )

                            publishers_list = []
                            year_efficiency_list = []
                            year_span_list = []

                            for (
                                each_publisher,
                                each_percent_list,
                            ) in pubs_per_faculty_percent.items():
                                for timespan_index, each_timespan in enumerate(
                                    pubs_per_faculty_in_range.keys()
                                ):
                                    publishers_list.append(each_publisher)
                                    year_efficiency_list.append(
                                        each_percent_list[timespan_index]
                                    )
                                    year_span_list.append(each_timespan)

                            graph_df = pd.DataFrame(
                                {
                                    "Year": year_span_list,
                                    "Efficiency": year_efficiency_list,
                                    "Publisher": publishers_list,
                                }
                            )

                            fig = px.bar(
                                graph_df, x="Year", y="Efficiency", color="Publisher"
                            )
                            fig.update_xaxes(tickangle=90)
                            return fig

                    with ui.nav_panel("Potential Compare (Select up to 1)"):

                        @render_plotly
                        def plot_faculty_productivity_sidebyside():
                            """Plot the efficiency of selected publishers side-by-side for comparison purposes"""
                            req(input.file1())
                            selected_names = get_selected_publishers(True)
                            if len(selected_names) > 1:
                                selected_names = selected_names[0:1]
                            date_year_ranges = get_selected_timespan_year_bins()
                            pub_counts_per_publisher_over_time = (
                                determine_pubs_per_publisher_overtime()
                            )

                            pubs_per_faculty_in_range = (
                                determine_pubs_per_faculty_range(
                                    date_year_ranges,
                                    selected_names,
                                    pub_counts_per_publisher_over_time,
                                )
                            )
                            pubs_per_faculty_percent = determine_faculty_pubs_percents(
                                pubs_per_faculty_in_range, selected_names
                            )

                            pubs_per_faculty_percent.update(
                                determine_med_max_min("Median")
                            )

                            pubs_per_faculty_percent.update(
                                determine_med_max_min("Maximum")
                            )

                            publishers_list = []
                            year_efficiency_list = []
                            year_span_list = []

                            for (
                                each_publisher,
                                each_percent_list,
                            ) in pubs_per_faculty_percent.items():
                                for timespan_index, each_timespan in enumerate(
                                    pubs_per_faculty_in_range.keys()
                                ):
                                    publishers_list.append(each_publisher)
                                    year_efficiency_list.append(
                                        each_percent_list[timespan_index]
                                    )
                                    year_span_list.append(each_timespan)

                            graph_df = pd.DataFrame(
                                {
                                    "Year": year_span_list,
                                    "Efficiency": year_efficiency_list,
                                    "Publisher": publishers_list,
                                }
                            )

                            fig = px.bar(
                                graph_df,
                                x="Year",
                                y="Efficiency",
                                color="Publisher",
                                barmode="group",
                            )
                            fig.update_xaxes(tickangle=90)
                            return fig

    with ui.nav_panel("Raw Data"):

        @render.data_frame
        def raw_publication_data_df():
            """Display raw data in a grid for observing and filtering"""
            req(input.file1())
            raw_data = read_in_file_all_data()
            if raw_data is not None:
                return render.DataGrid(
                    raw_data,
                    filters=True,
                    width="100%",
                    height="600px",
                    styles=df_data_styles,
                )

    with ui.nav_panel("Publisher Data"):

        @render.data_frame
        def raw_publisher_data_df():
            """Display publisher data in a grid for observing and filtering"""
            req(input.file1())
            raw_publisher_data = read_in_file_publisher_data()
            if raw_publisher_data is not None:
                df = raw_publisher_data.copy()
                temp_cols = []
                top_headers = 5
                for i in range(top_headers):
                    temp_cols.append(df.columns[i][0])
                for j in range(top_headers, len(df.columns)):
                    temp_cols.append(str(df.columns[j][1]) + " Research %")
                df.columns = temp_cols
                return render.DataGrid(df, filters=True, width="100%", height="600px")
