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
  extend: qx.ui.core.Widget,
  implement: [qx.ui.form.IModel, osparc.filter.IFilterable],
  include: [qx.ui.form.MModelProperty, osparc.filter.MFilterable],
  type: "abstract",

  construct: function() {
    this.base(arguments);

    this.set({
      width: osparc.dashboard.GridButtonBase.ITEM_WIDTH,
      minHeight: this.self().HEIGHT,
      padding: 5,
      alignY: "middle"
    });

    const gridLayout = new qx.ui.layout.Grid();
    gridLayout.setSpacing(this.self().SPACING);
    gridLayout.setColumnFlex(this.self().POS.TITLE.column, 1);
    gridLayout.setColumnAlign(this.self().POS.ICON.column, "center", "middle");
    gridLayout.setColumnAlign(this.self().POS.TITLE.column, "left", "middle");
    this._setLayout(gridLayout);

    this.addListener("pointerover", this.__onPointerOver, this);
    this.addListener("pointerout", this.__onPointerOut, this);
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
    HEIGHT: 50,
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
    },
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
      return false;
    },

    _shouldReactToFilter: function(data) {
      return false;
    }
  },

  destruct: function() {
    this.removeListener("pointerover", this.__onPointerOver, this);
    this.removeListener("pointerout", this.__onPointerOut, this);
  }
});
