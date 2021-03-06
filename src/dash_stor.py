from itertools import cycle

from bokeh.plotting import figure
from bokeh.layouts import layout, gridplot
from bokeh.models.widgets import (
    Button, RadioButtonGroup, Spinner,
    Slider, RangeSlider, Select
)
from bokeh.models.widgets.tables import DataTable, TableColumn, NumberFormatter
from bokeh.models.callbacks import CustomJS, OpenURL
from bokeh.models.markers import Circle
from bokeh.models.annotations import ColorBar, LabelSet
from bokeh.models.tools import HoverTool, TapTool
from bokeh.models.tickers import LogTicker
from bokeh.transform import log_cmap, jitter
from bokeh.palettes import viridis as gen_palette

from src.helpers import load_tooltip


class StorageDash():
    """
    A dashboard that displays single material data.

    Pass a reference to the Bokeh document for threading access.
    """

    def __init__(self, model):
        """
        Construct storage dashboard
        """
        # Save reference to model
        self.model = model

        ################################
        # Process button
        ################################

        self.process = Button(
            label="Generate", button_type="primary",
            name='process', sizing_mode='scale_width')
        self.process.js_on_click(CustomJS(code="toggleLoading()"))

        ################################
        # Widgets
        ################################

        # Data type selection
        self.data_type = RadioButtonGroup(
            labels=["All Data", "Experimental", "Simulated"],
            active=0, css_classes=['dtypes'])

        # Adsorbate drop-down selections
        self.g1_sel = Select(title="Adsorbate 1",
                             options=self.model.ads_list, value=self.model.g1,
                             css_classes=['g-selectors'])

        # Temperature selection
        self.t_absolute = Spinner(
            value=303, title='Temperature:', css_classes=['t_abs'])
        self.t_tolerance = Spinner(
            value=10, title='Tolerance:', css_classes=['t_tol'])

        # Combined in a layout
        self.dsel_widgets = layout([
            [self.data_type],
            [self.g1_sel, self.g2_sel, self.t_absolute, self.t_tolerance],
        ], sizing_mode='scale_width', name="widgets")

        ################################
        # KPI Plots
        ################################

        # Top graph generation
        tooltip = load_tooltip()
        self.p_henry, rend1 = self.top_graph(
            "K", "Henry coefficient (log)",
            self.model.data, self.model.errors, tooltip)
        self.p_loading, rend2 = self.top_graph(
            "L", "Uptake at selected pressure",
            self.model.data, self.model.errors, tooltip)
        self.p_wc, rend3 = self.top_graph(
            "W", "Working capacity in selected range",
            self.model.data, self.model.errors, tooltip)

        # Give graphs the same hover and select effect
        sel = Circle(fill_alpha=1, fill_color="red", line_color='black')
        for rend in [rend1, rend2, rend3]:
            rend.selection_glyph = sel
            rend.hover_glyph = sel

        # Pressure slider
        self.p_slider = Slider(title="Pressure (bar)", value=0.5,
                               start=0, end=20, step=0.5,
                               callback_policy='throttle',
                               callback_throttle=500,
                               )

        # Working capacity slider
        self.wc_slider = RangeSlider(title="Working capacity (bar)",
                                     value=(0.5, 5),
                                     start=0, end=20, step=0.5,
                                     callback_policy='throttle',
                                     callback_throttle=500,
                                     )

        # Material datatable
        self.mat_list = DataTable(
            columns=[
                TableColumn(field="labels", title="Material", width=300),
                TableColumn(field="sel", title="KH2/KH1", width=25,
                            formatter=NumberFormatter(format='‘0.0a’')),
                TableColumn(field="psa_W", title="PSA-API", width=30,
                            formatter=NumberFormatter(format='‘0.0a’')),
            ],
            source=self.model.data,
            index_position=None,
            selectable='checkbox',
            scroll_to_selection=True,
            width=400,
            fit_columns=True,
        )

        # Custom css classes for interactors
        self.p_henry.css_classes = ['g-henry']
        self.p_loading.css_classes = ['g-load']
        self.p_wc.css_classes = ['g-wcap']
        self.mat_list.css_classes = ['t-details']

        # Generate the axis labels
        self.top_graph_labels()

        self.kpi_plots = layout([
            [gridplot([
                [self.mat_list, self.p_henry],
                [self.p_loading, self.p_wc]], sizing_mode='scale_width')],
            [self.p_slider, self.wc_slider],
        ], sizing_mode='scale_width', name="kpiplots")
        self.kpi_plots.children[0].css_classes = ['kpi']
        self.kpi_plots.children[1].css_classes = ['p-selectors']

        ################################
        # Isotherm details explorer
        ################################

        # Isotherm display graphs
        self.p_g1iso = self.bottom_graph(self.model.g1_iso_sel, self.model.g1)
        self.p_g2iso = self.bottom_graph(self.model.g2_iso_sel, self.model.g2)

        # Isotherm display palette
        self.c_cyc = cycle(gen_palette(20))

        self.detail_plots = layout([
            [self.p_g1iso, self.p_g2iso],
        ], sizing_mode='scale_width', name="detailplots")
        self.detail_plots.children[0].css_classes = ['isotherms']

    # #########################################################################
    # Graph generators

    def top_graph(self, ind, title, data, errors, tooltip, **kwargs):
        """Generate the top graphs (KH, uptake, WC)."""

        # Generate figure dict
        plot_side_size = 400
        fig_dict = dict(tools="pan,wheel_zoom,tap,reset,save",
                        active_scroll="wheel_zoom",
                        plot_width=plot_side_size,
                        plot_height=plot_side_size,
                        title=title, y_range=['Materials'])

        # Create a colour mapper for number of isotherms
        mapper = log_cmap(
            field_name='{0}_nx'.format(ind), palette="Viridis256",
            low_color='grey', high_color='yellow',
            low=3, high=100)

        # Create a new plot
        graph = figure(**fig_dict)

        # Add the hover tooltip
        graph.add_tools(HoverTool(
            names=["{0}_data".format(ind)],
            tooltips=tooltip.render(p=ind))
        )

        # Plot the data
        rend = graph.circle(
            "{0}_x".format(ind), y=jitter('{0}_nx'.format(ind), width=0.6, range=graph.y_range),
            source=data, size=10,
            line_color=mapper, color=mapper,
            name="{0}_data".format(ind)
        )

        # Plot the error margins
        # graph.segment(
        #     '{0}_x0'.format(ind), '{0}_y0'.format(ind),
        #     '{0}_x1'.format(ind), '{0}_y1'.format(ind),
        #     source=errors,
        #     color="black", line_width=2,
        #     line_cap='square', line_dash='dotted')

        # Plot labels next to selected materials
        # graph.add_layout(LabelSet(
        #     x='{0}_x'.format(ind), y='{0}_y'.format(ind),
        #     source=errors,
        #     text='labels', level='glyph',
        #     x_offset=5, y_offset=5,
        #     render_mode='canvas',
        #     text_font_size='8pt',
        # ))

        # Add the colorbar to the side
        graph.add_layout(ColorBar(
            color_mapper=mapper['transform'],
            ticker=LogTicker(desired_num_ticks=10),
            width=8, location=(0, 0)),
            'right'
        )

        return graph, rend

    def top_graph_labels(self):
        """Generate the top graph labels from selected ads_list."""
        self.p_loading.xaxis.axis_label = '{0} (mmol/g)'.format(self.model.g1)
        self.p_henry.xaxis.axis_label = '{0} (mmol/bar)'.format(self.model.g1)
        self.p_wc.xaxis.axis_label = '{0} (mmol/g)'.format(self.model.g1)

    def bottom_graph(self, source, ads):
        """Generate the bottom graphs (isotherm display)."""

        graph = figure(tools="pan,wheel_zoom,tap,reset",
                       active_scroll="wheel_zoom",
                       plot_width=400, plot_height=250,
                       x_range=(-0.1, 1), y_range=(-0.1, 1),
                       title='Isotherms {0}'.format(ads))
        rend = graph.multi_line('x', 'y', source=source,
                                alpha=0.6, line_width=3,
                                hover_line_alpha=1.0,
                                hover_line_color="black",
                                line_color='color')

        # Make clicking a graph oben the NIST database
        url = "https://adsorption.nist.gov/isodb/index.php?DOI=@doi#biblio"
        graph.add_tools(TapTool(renderers=[rend],
                                callback=OpenURL(url=url)))
        graph.add_tools(HoverTool(show_arrow=False,
                                  line_policy='nearest',
                                  tooltips=[
                                      ('Label', '@labels'),
                                      ('T (K)', '@temp'),
                                  ]))

        graph.xaxis.axis_label = 'Pressure (bar)'
        graph.yaxis.axis_label = 'Uptake (mmol/g)'

        return graph
