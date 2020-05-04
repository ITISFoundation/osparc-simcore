/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 */

qx.Class.define("osparc.component.widget.OrganizationListItem", {
  extend: qx.ui.core.Widget,
  implement: qx.ui.form.IModel,
  include: qx.ui.form.MModelProperty,

  construct: function() {
    this.base(arguments);

    const layout = new qx.ui.layout.HBox();
    this._setLayout(layout);
  },

  properties: {
    gid: {
      check: "String",
      nullable: false
    },

    label: {
      check: "String",
      apply: "_applyLabel",
      nullable: false
    },

    description: {
      check: "String",
      init: "",
      apply: "_applyDescription",
      nullable: true
    }
  },

  members: {

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "label":
          control = new qx.ui.basic.Label().set({
            font: osparc.utils.Utils.getFont(14, true),
            alignY: "bottom"
          });
          this._add(control);
          break;
        case "description":
          control = new qx.ui.basic.Label().set({
            font: osparc.utils.Utils.getFont(12),
            alignY: "bottom"
          });
          this._add(control, {
            flex: 1
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    _applyLabel: function(value) {
      if (value === null) {
        return;
      }
      const label = this.getChildControl("label");
      label.setValue(value);
    },

    _applyDescription: function(value) {
      if (value === null) {
        return;
      }
      const label = this.getChildControl("description");
      label.setValue(": " + value);
    }
  }
});
