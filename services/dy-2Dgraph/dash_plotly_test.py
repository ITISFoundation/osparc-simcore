import dash
import dash_core_components as dcc
import dash_html_components as html
import pandas as pd
import plotly.graph_objs as go

app = dash.Dash()

column_name_map = {0: {"name":"time [s]"}, 1: {"name":"rate"}, 2: {"name":"demand"}, 
                    3: {"name":"move/(max - min) sympathetic efferent", "scale":1/0.0008}, 
                    4: {"name":"threshold indirect parasympathetic efferent"},
                   5: {"name":"direct parasympathetic efferent", "scale":1/0.0008}, 
                   6: {"name":"rectruitment = coefficient of variation"}}
column_scaling = {}
data_frame = pd.read_csv(r'C:/Users/anderegg/Documents/dev/OSPARC/osparc-odei/demos/qooxdoo-plotly/app/source/class/app/data/outputControllerOut.dat',
                 sep=',',
                 header=None)


app.layout = html.Div([  
    html.Div([
        dcc.Dropdown(
            id="sorting-column-dropdown",
            options=[{"label":column_name_map[i]["name"],"value":column_name_map[i]["name"]} for i in range(0, data_frame.columns.size)],
            value=column_name_map[0]["name"]
        ),
        dcc.Graph(id='table'),
    ]),  
    html.Div([
        html.Div([
            dcc.RadioItems(
                id='xaxis-type',
                options=[{"label":i, "value": i} for i in ["Linear", "Log"]],
                value="Linear",
                labelStyle={"display":"inline-block"}
            )
        ], style={"width":"50%", 
                    "display":"inline-block"}),

        html.Div([
            dcc.RadioItems(
                id='yaxis-type',
                options=[{"label":i, "value": i} for i in ["Linear", "Log"]],
                value="Linear",
                labelStyle={"display":"inline-block"}
            )
        ], style={"width":"50%", 
                "float":"right", 
                "display":"inline-block"
                }),
    ], style={"padding": "10px 5px", 
            "border-bottom":"thin lightgrey solid",
            "backgroundColor":"rgb(250,250,250)"}),
    html.Div([
        dcc.Graph(id="graph")    
    ], style={"width":"100%",
        "padding":"0 20"})
])

@app.callback(dash.dependencies.Output("table", "figure"),
            [dash.dependencies.Input("sorting-column-dropdown", "value")])
def update_table(sort_column):
    
    column_index = [col for col, val in column_name_map.items() if val["name"] == sort_column]    
    sorted_data_frame = data_frame.sort_values(by=[column_index[0]])
    return {
            'data': [
                go.Table(
                    header=dict(
                        values=list(column_name_map[i]["name"] for i in range(0, sorted_data_frame.columns.size)),
                        fill=dict(color="#C2D4FF"),
                        align=["left"]
                    ),
                    cells=dict(
                        values=[sorted_data_frame[i] for i in range(0, sorted_data_frame.columns.size)],
                        fill=dict(color="#F5F8FF"),
                        align=["left"]
                    )
                ) 
            ]
        }

@app.callback(dash.dependencies.Output("graph", "figure"), 
            [dash.dependencies.Input("xaxis-type", "value"),
            dash.dependencies.Input("yaxis-type", "value")])
def update_graph(xaxis_type, yaxis_type):
    return {
        'data': [                
            go.Scatter(
                x=data_frame[0],
                y=data_frame[i] * (column_name_map[i]["scale"] if "scale" in column_name_map[i] else 1),
                opacity=0.5,                        
                name=column_name_map[i]["name"]
            ) for i in range(1,data_frame.columns.size)
        ],
        'layout': go.Layout(
            title="Heart Rate(r)",
            # xaxis={'type': 'log', 'title': 'time(sec)'},
            xaxis={'title': 'time(sec)',
                    "type": "linear" if xaxis_type == "Linear" else "log"},
            yaxis={'range': [0,.5],
                    "type": "linear" if yaxis_type == "Linear" else "log"},
            # margin={'l': 40, 'b': 40, 't': 10, 'r': 10},
            #legend={'x': 0, 'y': 1},
            # hovermode='closest'
        )
    }

if __name__ == '__main__':
    app.run_server()
