import os
import pandas as pd
import plotly.express as px
import sys
from IPython.display import display
from typing import List, Tuple

pd.set_option('display.max_rows', 15)
pd.set_option('display.max_columns', 5)
pd.set_option('display.width', 1000000)
pd.set_option('display.colheader_justify', 'center')
pd.set_option('display.precision', 3)


class DescribedDataFrame(pd.DataFrame):
    # normal properties
    _metadata = ["name", "description"]

    @property
    def _constructor(self):
        return DescribedDataFrame


def extract() -> Tuple[pd.Series, List[DescribedDataFrame]]:
    dataframe_container = []
    temp = pd.read_csv('data/data_dictionary.csv', encoding='latin')
    description = pd.Series(data=list(temp['Description']), index=temp['Field'])

    for csv_name in os.listdir("data/"):
        if not csv_name == "data_dictionary.csv":
            dataframe = DescribedDataFrame(pd.read_csv('data/' + csv_name, encoding='latin'))
            dataframe.name = csv_name.split('.csv')[0]
            dataframe_container.append(dataframe)
    return description, dataframe_container


def concat_dataframes(description: pd.Series, dataframe_container: List[DescribedDataFrame]) -> DescribedDataFrame:
    orders, order_details, pizzas, pizza_types = dataframe_container

    # Formatting orders' dates and times
    orders.set_index('order_id', inplace=True)
    orders = pd.to_datetime(orders['date'] + orders['time'], format='%d/%m/%Y%H:%M:%S')

    # Pizzas
    pizzas = pizzas[['pizza_id', 'price']].set_index('pizza_id')
    pizzas_dict = pizzas['price'].to_dict()

    # Not a very neat line of code, but when grouping by order_id, quantities are not taken into account. One solution
    # is duplicating each row by how many times the pizzas has been ordered.
    order_details = order_details.reindex(order_details.index.repeat(order_details['quantity'])).reset_index(drop=True)
    order_details = pd.DataFrame(order_details.groupby(['order_id'])['pizza_id'].apply(list), columns=["order_details"])
    order_details.index.name = 'order_id'

    def get_price_order(order: List[str]) -> float:
        return sum([pizzas_dict[pizza_id] for pizza_id in order])

    order_details['price'] = order_details['order_details'].map(get_price_order)

    # Creating our work-dataframe
    frame = {'Timestamp': orders, 'Order_details': order_details['order_details'], 'Price': order_details['price']}
    result = DescribedDataFrame(frame)
    result.name = 'summed_dataframe'
    result.description = description
    return result


def count_ingredients(dataframe: DescribedDataFrame, pizzas_dataframe: DescribedDataFrame) -> Tuple[pd.Series,
                                                                                                    pd.DataFrame]:
    pizzas_dataframe = pizzas_dataframe[['pizza_type_id', 'ingredients']].set_index('pizza_type_id')

    def check_missing_ingredients(ingredients: str):
        if 'Sauce' not in ingredients:
            ingredients += ', Tomato Sauce'
        if 'Mozzarella Cheese' not in ingredients:
            ingredients += ', Mozzarella Cheese'
        return ingredients

    pizzas_dataframe['ingredients'] = pizzas_dataframe['ingredients'].apply(check_missing_ingredients)
    pizzas_dataframe['ingredients'] = pizzas_dataframe['ingredients'].apply(lambda string: string.split(', '))
    pizzas_dict = pizzas_dataframe['ingredients'].to_dict()

    def get_ingredients(order_details: List[str]) -> List[str]:
        total_ingredients_list = []
        for ingredients_list in [pizzas_dict[pizza.rsplit('_', 1)[0]] for pizza in order_details]:
            total_ingredients_list += ingredients_list
        return total_ingredients_list

    dataframe['Ingredients'] = dataframe['Order_details'].apply(get_ingredients)

    # Get total count of each ingredient
    temp = pd.Series([item for sublist in dataframe['Ingredients'] for item in sublist])
    total_count = temp.groupby(temp).size()
    total_count.name = "Total_Count"
    total_count.index.name = "ingredient"

    # Separate by weeks
    weeks = pd.DataFrame(dataframe.groupby([dataframe['Timestamp'].dt.strftime('%W')])['Ingredients'].apply(sum))
    weeks = weeks.rename(columns={"summed_dataframe": "Ingredients"})
    weeks.index.name = "week"

    weeks = weeks.explode('Ingredients').pivot_table(index="week", columns='Ingredients', aggfunc="size", fill_value=0)
    weeks.reset_index(inplace=True)
    weeks['week'] = weeks['week'].apply(int)
    return total_count, weeks


def visualize_ingredients_consumed(series: pd.Series, dataframe: pd.DataFrame) -> None:
    # Amount of total ingredients consumed by each type
    series.sort_values(ascending=False, inplace=True)
    fig = px.bar(series, labels={'ingredient': 'Ingredient', 'value': 'Amount consumed'},
                 title='Amount of total ingredients consumed over a year by each Type',
                 color="value", template='ggplot2')
    fig.update_layout(showlegend=False)
    fig.update_xaxes(tickangle=60)
    fig.show()

    # Amount and type of ingredients consumed each week
    dataframe = dataframe.melt(id_vars='week', value_vars=dataframe.columns[1:])
    display(dataframe)
    fig = px.bar(dataframe, x='value', y='Ingredients', labels={'value': 'Amount consumed'},
                 title='Amount of total ingredients consumed per week by each Type',
                 color="value", template='ggplot2', animation_frame='week', height=950)
    fig.update_layout(showlegend=False)
    fig.update_xaxes(tickangle=60)
    fig.show()
    return


def main():
    description, dataframe_container = extract()

    # Creating main dataframe to work with.
    dataframe = concat_dataframes(description, dataframe_container)
    dataframe.to_csv("processed_data/clean_dataframe.csv", sep=',')
    display(dataframe)
    # display(dataframe.describe())

    # Now let's create some useful dataframes to solve our problem.
    # Amount of total ingredients consumed by each type
    pizza_types = dataframe_container[-1]
    total_count, weeks = count_ingredients(dataframe, pizza_types)
    display(total_count)

    # Amount and type of ingredients consumed each week
    weeks.to_csv("processed_data/ingredients_weeks.csv", sep=',')
    display(weeks)

    visualize_ingredients_consumed(total_count, weeks)


if __name__ == '__main__':
    sys.exit(main())