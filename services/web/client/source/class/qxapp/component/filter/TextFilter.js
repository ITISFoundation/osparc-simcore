/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * Label and TextField meant for filtering
 */
qx.Class.define("qxapp.component.filter.TextFilter", {
  extend: qx.ui.core.Widget,

  construct: function(filterId, labelId = "Filter") {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox());

    this.__filterId = filterId;
    this._add(new qx.ui.basic.Label(this.tr(labelId) + ":").set({
      appearance: "toolbar-label"
    }));
    const textField = this.__textField = new qx.ui.form.TextField().set({
      appearance: "toolbar-textfield"
    });
    this._add(textField);

    this.__attachEventHandlers();
  },

  members: {
    __filterId: null,
    __textField: null,
    __attachEventHandlers: function() {
      this.__textField.addListener("input", evt => {
        // Do something
      });
    }
  }
});
