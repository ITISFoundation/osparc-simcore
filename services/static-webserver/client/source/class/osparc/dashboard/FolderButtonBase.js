/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.FolderButtonBase", {
  extend: qx.ui.form.ToggleButton,
  implement: [qx.ui.form.IModel, osparc.filter.IFilterable],
  include: [qx.ui.form.MModelProperty, osparc.filter.MFilterable],
  type: "abstract",

  construct: function() {
    this.base(arguments);

    this.set({
      width: osparc.dashboard.GridButtonBase.ITEM_WIDTH,
      minHeight: osparc.dashboard.ListButtonBase.ITEM_HEIGHT,
      padding: 5
    });

    const layout = new qx.ui.layout.Grid();
    layout.setSpacing(this.self().SPACING);
    layout.setColumnFlex(this.self().POS.TITLE.column, 1);
    this._setLayout(layout);

    [
      "pointerover",
      "focus"
    ].forEach(e => this.addListener(e, this.__onPointerOver, this));

    [
      "pointerout",
      "focusout"
    ].forEach(e => this.addListener(e, this.__onPointerOut, this));
  },

  properties: {
    cardKey: {
      check: "String",
      nullable: true
    },

    resourceType: {
      check: ["folder"],
      init: "folder",
      nullable: false
    },

    priority: {
      check: "Number",
      init: null,
      nullable: false
    }
  },

  statics: {
    SPACING: 5,
    POS: {
      ICON: {
        column: 0,
        row: 0,
        rowSpan: 2
      },
      TITLE: {
        column: 1,
        row: 0
      },
      SUBTITLE: {
        column: 1,
        row: 1
      },
      MENU: {
        column: 2,
        row: 0,
        rowSpan: 2
      }
    }
  },

  members: { // eslint-disable-line qx-rules/no-refs-in-members
    // overridden
    _forwardStates: {
      focused : true,
      hovered : true,
      selected : true,
      dragover : true
    },

    __onPointerOver: function() {
      this.addState("hovered");
    },

    __onPointerOut : function() {
      this.removeState("hovered");
    },

    _filter: function() {
      this.exclude();
    },

    _unfilter: function() {
      this.show();
    },

    _shouldApplyFilter: function(data) {
      console.log("_shouldApplyFilter", data);
      return false;
    },

    _shouldReactToFilter: function(data) {
      console.log("_shouldReactToFilter", data);
      return false;
    }
  },

  destruct: function() {
    this.removeListener("pointerover", this.__onPointerOver, this);
    this.removeListener("pointerout", this.__onPointerOut, this);
  }
});
