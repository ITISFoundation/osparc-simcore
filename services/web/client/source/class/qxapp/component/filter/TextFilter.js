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
 * Label and TextField bundled together to make a simple text filter.
 */
qx.Class.define("qxapp.component.filter.TextFilter", {
  extend: qxapp.component.filter.UIFilter,

  construct: function(filterId, groupId, labelTr = "Filter") {
    this.base(arguments, filterId, groupId);
    this._setLayout(new qx.ui.layout.HBox());

    this._add(new qx.ui.basic.Label(this.tr(labelTr) + ":").set({
      appearance: "toolbar-label"
    }));
    const textField = this.__textField = new qx.ui.form.TextField().set({
      appearance: "toolbar-textfield"
    });
    this._add(textField);

    this.__attachEventHandlers();
  },

  members: {
    __textField: null,

    __attachEventHandlers: function() {
      this.__textField.addListener("input", evt => {
        this._filterChange(evt.getData().trim().toLowerCase());
      });
    }
  }
});
