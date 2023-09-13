/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.product.quickStart.ti.PostPro", {
  extend: osparc.product.quickStart.SlideBase,

  construct: function() {
    const title = this.tr("Post Processing");
    this.base(arguments, title);
  },

  members: {
    _populateCard: function() {
      const text1 = this.tr("\
        Based on extensive sweeping/optimization, a series of highly performing exposure parameters are proposed for the \
        user to interactively explore, using predefined quantification metrics and visualizations. Identified \
        conditions-of-interest can be documented and added to a report.\
      ");
      const label1 = osparc.product.quickStart.Utils.createLabel(text1);
      this._add(label1);

      const text2 = this.tr("\
        These metrics are reported in the Post Processing analysis environment for each electrode pair in the combination in \
        a sorted tabular form that can be used to inspect the stimulation performances. By clicking on each pair, slice views \
        of the maximum amplitude modulation (MAP) within the head are produced.<br>\
        Pressing the `Load` button on the right, the selected configuration will be loaded.\
      ");
      const label2 = osparc.product.quickStart.Utils.createLabel(text2);
      this._add(label2);

      const image1 = new qx.ui.basic.Image("https://itisfoundation.github.io/ti-planning-tool-manual/assets/quickguide/postpro_gui_1.gif").set({
        alignX: "center",
        scale: true,
        width: 740,
        height: 538
      });
      this._add(image1);

      const text3 = this.tr("\
        Alternatively, slice views of the maximum interferential E-field can also be visualized and synchronous with the MAP slices \
        to assess safety-related aspects (e.g., field intensity in proximity of the electrodes). These maps can be edited, thresholded, \
        and saved offline for further inspection and analysis.<br>\
        An isosurface of the TI stimulation distribution for the selected configuration can also be visualized within the head anatomy for inspection.\
      ");
      const label3 = osparc.product.quickStart.Utils.createLabel(text3);
      this._add(label3);

      const image2 = new qx.ui.basic.Image("https://itisfoundation.github.io/ti-planning-tool-manual/assets/quickguide/postpro_gui_2.gif").set({
        alignX: "center",
        scale: true,
        width: 740,
        height: 520
      });
      this._add(image2);

      const text4 = this.tr("\
        At the end of the optimization procedure, you can automatically generate a report.<br>\
        It includes a summary of all the performance metrics calculated for each electrode pair combination, and a detailed performance report \
        of the optimized electrode configuration. The report includes electrode placement, current intensities, performance metrics, TI and maximum \
        high-frequency field distributions, cumulative dose histograms and all the graphs generated in the post-pro analysis tab.\
      ");
      const label4 = osparc.product.quickStart.Utils.createLabel(text4);
      this._add(label4);

      const image3 = new qx.ui.basic.Image("https://itisfoundation.github.io/ti-planning-tool-manual/assets/quickguide/postpro_gui_3.gif").set({
        alignX: "center",
        scale: true,
        width: 740,
        height: 520
      });
      this._add(image3);
    }
  }
});
