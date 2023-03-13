/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2023 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

/**
 * Button to toggle the selection of one collaborator
 */
qx.Class.define("osparc.component.filter.CollaboratorToggleButton", {
  extend: qx.ui.form.ToggleButton,
  include: osparc.component.filter.MFilterable,
  implement: osparc.component.filter.IFilterable,

  construct: function(collaborator) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox(8).set({
      alignY: "middle"
    }));
    this.set({
      minHeight: 30,
      appearance: "tagbutton"
    });

    this.setLabel(collaborator["label"]);
    let iconPath = null;
    switch (collaborator["collabType"]) {
      case 0:
        iconPath = "@FontAwesome5Solid/globe/14";
        break;
      case 1:
        iconPath = "@FontAwesome5Solid/users/14";
        break;
      case 2:
        iconPath = "@FontAwesome5Solid/user/14";
        break;
    }
    this.setIcon(iconPath);

    this.getChildControl("check");
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "label":
          control = new qx.ui.basic.Label(this.getLabel()).set({
            allowStretchX: true
          });
          control.setAnonymous(true);
          control.setRich(this.getRich());
          this._add(control, {
            flex: 1
          });
          if (this.getLabel() == null || this.getShow() === "icon") {
            control.exclude();
          }
          break;
        case "check":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/check/14");
          control.setAnonymous(true);
          this._add(control);
          this.bind("value", control, "visibility", {
            converter: value => value ? "visible" : "hidden"
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    _filter: function() {
      this.exclude();
    },

    _unfilter: function() {
      this.show();
    },

    _shouldApplyFilter: function(data) {
      if (data.name) {
        // data.name comes lowercased
        if (!this.getLabel().toLowerCase().includes(data.name)) {
          return true;
        }
      }
      return false;
    },

    _shouldReactToFilter: function(data) {
      if (data.name && data.name.length > 1) {
        return true;
      }
      return false;
    }
  }
});
