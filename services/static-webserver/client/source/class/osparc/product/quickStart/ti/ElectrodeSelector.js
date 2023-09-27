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

qx.Class.define("osparc.product.quickStart.ti.ElectrodeSelector", {
  extend: osparc.product.quickStart.SlideBase,

  construct: function() {
    const title = this.tr("Electrode Selector");
    this.base(arguments, title);
  },

  members: {
    _populateCard: function() {
      const text1 = this.tr("\
        After pressing New Plan, three panels will be shown.\
      ");
      const label1 = osparc.product.quickStart.Utils.createLabel(text1);
      this._add(label1);

      const text2 = this.tr("\
        In a first step, the relevant species, stimulation target, electrode shapes, electrode dimensions and \
        potential electrode locations (currently required to narrow down the huge exposure configuration search space) are selected.\
      ");
      const label2 = osparc.product.quickStart.Utils.createLabel(text2);
      this._add(label2);

      const image = new qx.ui.basic.Image("https://itisfoundation.github.io/ti-planning-tool-manual/assets/quickguide/electrode_selector.gif").set({
        alignX: "center",
        scale: true,
        width: 737,
        height: 540
      });
      this._add(image);

      const text4 = this.tr("\
        After finishing the set up, the big button on the top right will turn blue and by clicking on it you will submit the configuration.\
      ");
      const label4 = osparc.product.quickStart.Utils.createLabel(text4);
      this._add(label4);

      const text5 = this.tr("\
        Now the Arrow that says 'Next' can be pushed and the optimization will inmediatly start.\
      ");
      const label5 = osparc.product.quickStart.Utils.createLabel(text5);
      this._add(label5);
    }
  }
});
