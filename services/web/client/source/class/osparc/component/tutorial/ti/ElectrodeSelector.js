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

qx.Class.define("osparc.component.tutorial.ti.ElectrodeSelector", {
  extend: osparc.component.tutorial.ti.SlideBase,

  construct: function() {
    const title = this.tr("Electrode Selector");
    this.base(arguments, title);
  },

  members: {
    _populateCard: function() {
      this._add(new qx.ui.basic.Label().set({
        value: this.tr("\
        After pressing New Plan, three panels will be shown\
        "),
        rich: true,
        wrap: true,
        font: "text-14"
      }));

      this._add(new qx.ui.basic.Label().set({
        value: this.tr("\
        In a first step, the relevant species, stimulation target, and potential electrode locations \
        (currently required to narrow down the huge exposure configuration search space) are selected.\
        "),
        rich: true,
        wrap: true,
        font: "text-14"
      }));

      const image = new qx.ui.basic.Image("osparc/tutorial/ti/ElectrodeSelector.gif").set({
        alignX: "center",
        scale: true,
        width: 737,
        height: 540
      });
      this._add(image);

      this._add(new qx.ui.basic.Label().set({
        value: this.tr("\
        After finishing the set up, click on the big button on the top right to submit the configuration.\
        "),
        rich: true,
        wrap: true,
        font: "text-14"
      }));

      this._add(new qx.ui.basic.Label().set({
        value: this.tr("\
        Now the Arrow that says 'Next' can be pushed and the optimization will inmediatly start.\
        "),
        rich: true,
        wrap: true,
        font: "text-14"
      }));
    }
  }
});
