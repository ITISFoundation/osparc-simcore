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

    let iconPath = null;
    let label = null;
    let toolTipText = "";
    switch (collaborator["collabType"]) {
      case 0:
        iconPath = "@FontAwesome5Solid/globe/14";
        label = this.tr("Public");
        toolTipText = this.tr("Public to all users");
        break;
      case 1:
        iconPath = "@FontAwesome5Solid/users/14";
        label = collaborator.getLabel();
        toolTipText = collaborator.getDescription();
        break;
      case 2: {
        iconPath = "@FontAwesome5Solid/user/14";
        label = collaborator.getLabel();
        if (collaborator.getEmail()) {
          toolTipText += collaborator.getEmail() + "<br>";
        }
        if (collaborator.getFirstName()) {
          toolTipText += [collaborator.getFirstName(), collaborator.getLastName()].join(" ").trim();
        }
        break;
      }
    }
    this.setIcon(iconPath);
    this.setLabel(label);
    if (toolTipText) {
      const infoButton = new osparc.ui.hint.InfoHint(toolTipText);
      this._add(infoButton);
    }

    this.getChildControl("check");
  },

  properties: {
    iconSrc: {
      check: "String",
      nullable: true,
      init: "@FontAwesome5Solid/check/14",
      event: "changeIconSrc"
    },
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
          control = new qx.ui.basic.Image();
          this.bind("iconSrc", control, "source");
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
