/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2023 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

/**
 * Button to toggle the selection of one collaborator
 */
qx.Class.define("osparc.filter.CollaboratorToggleButton", {
  extend: qx.ui.form.ToggleButton,
  include: osparc.filter.MFilterable,
  implement: osparc.filter.IFilterable,

  construct: function(collaborator) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox(8).set({
      alignY: "middle"
    }));
    this.set({
      minHeight: 30,
      appearance: "tagbutton"
    });

    let label = collaborator.getLabel();
    if ("getLogin" in collaborator) {
      // user
      label += ` (${collaborator.getLogin()})`;
      this.setToolTipText(collaborator.getLogin());
    }
    this.setLabel(label);

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

    __filterText: function(text) {
      const checks = [
        this.getLabel(),
        this.getToolTipText()
      ];
      if (text) {
        const includesSome = checks.some(check => (check !== null) && check.toLowerCase().trim().includes(text.toLowerCase()));
        return !includesSome;
      }
      return false;
    },

    _shouldApplyFilter: function(data) {
      if (data.name) {
        // data.name comes lowercased
        return this.__filterText(data.name);
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
