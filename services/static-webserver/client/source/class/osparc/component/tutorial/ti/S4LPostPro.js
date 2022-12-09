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

qx.Class.define("osparc.component.tutorial.ti.S4LPostPro", {
  extend: osparc.component.tutorial.SlideBase,

  construct: function() {
    const title = this.tr("Sim4Life Post Processing");
    this.base(arguments, title);
  },

  members: {
    _populateCard: function() {
      const text1 = this.tr("\
        Finally, and optionally, exposure conditions-of-interest can be visualized and analyzed freely, using the web-version of the \
        Sim4Life (ZMT Zurich MedTech AG) computational life sciences platform.\
      ");
      const label1 = osparc.component.tutorial.Slides.createLabel(text1);
      this._add(label1);

      const image1 = new qx.ui.basic.Image("https://itisfoundation.github.io/ti-planning-tool-manual/assets/quickguide/postpro_s4l.gif").set({
        alignX: "center",
        scale: true,
        width: 737,
        height: 443
      });
      this._add(image1);
    }
  }
});
