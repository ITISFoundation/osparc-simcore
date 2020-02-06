/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Button to toggle the selection of one tag
 */
qx.Class.define("osparc.component.form.tag.TagToggleButton", {
  extend: qx.ui.form.ToggleButton,
  include: osparc.component.filter.MFilterable,
  implement: osparc.component.filter.IFilterable,
  construct: function(tag, value) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox(8).set({
      alignY: "middle"
    }));
    this.set({
      minHeight: 35,
      appearance: "tagbutton"
    });
    this.setIcon("@FontAwesome5Solid/square/14");
    this.getChildControl("icon").setTextColor(tag.color);
    this.setLabel(tag.name);
    this.getChildControl("check");

    this.setValue(value ? true : false); // eslint-disable-line no-unneeded-ternary
  },
  properties: {
    fetching: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeFetching",
      apply: "_applyFetching"
    }
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
          if (this.getLabel() == null || this.getShow() === "icon") { // eslint-disable-line no-eq-null
            control.exclude();
          }
          break;
        case "check":
          control = new qx.ui.basic.Image();
          control.setAnonymous(true);
          this._add(control);
          this.bind("value", control, "visibility", {
            converter: value => value ? "visible" : "hidden"
          });
          this.bind("fetching", control, "source", {
            converter: isFetching =>
              isFetching ?
                "@FontAwesome5Solid/circle-notch/14" :
                "@FontAwesome5Solid/check/14"
          });
          break;
      }
      return control || this.base(arguments, id);
    },
    _applyFetching: function(isFetching) {
      const check = this.getChildControl("check");
      if (isFetching) {
        check.show();
        check.getContentElement().addClass("rotate");
      } else {
        check.setVisibility(this.getValue() ? "visible" : "hidden");
        check.getContentElement().removeClass("rotate");
      }
    },

    _filter: function() {
      this.exclude();
    },

    _unfilter: function() {
      this.show();
    },

    _shouldApplyFilter: function(data) {
      if (data.name) {
        if (!this.getLabel().includes(data.name)) {
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
