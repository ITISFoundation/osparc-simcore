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

qx.Class.define("osparc.vipMarket.AnatomicalModelListItem", {
  extend: qx.ui.core.Widget,
  implement : [qx.ui.form.IModel, osparc.filter.IFilterable],
  include : [qx.ui.form.MModelProperty, osparc.filter.MFilterable],

  construct: function() {
    this.base(arguments);

    const layout = new qx.ui.layout.Grid(5, 5);
    layout.setColumnWidth(0, 64);
    layout.setRowFlex(0, 1);
    layout.setColumnFlex(1, 1);
    layout.setColumnAlign(0, "center", "middle");
    layout.setColumnAlign(1, "left", "middle");
    this._setLayout(layout);

    this.set({
      padding: 5,
      height: 48,
      alignY: "middle",
      decorator: "rounded",
    });

    this.addListener("pointerover", this._onPointerOver, this);
    this.addListener("pointerout", this._onPointerOut, this);
  },

  events: {
    /** (Fired by {@link qx.ui.form.List}) */
    "action" : "qx.event.type.Event"
  },

  properties: {
    appearance: {
      refine: true,
      init: "selectable"
    },

    modelId: {
      check: "Number",
      init: null,
      nullable: false,
      event: "changemodelId",
    },

    thumbnail: {
      check: "String",
      init: null,
      nullable: true,
      event: "changeThumbnail",
      apply: "__applyThumbnail",
    },

    name: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeName",
      apply: "__applyName",
    },

    date: {
      check: "Date",
      init: null,
      nullable: true,
      event: "changeDate",
    },

    leased: {
      check: "Boolean",
      init: false,
      nullable: true,
      event: "changeLeased",
      apply: "__applyLeased",
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

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "thumbnail":
          control = new qx.ui.basic.Image().set({
            alignY: "middle",
            scale: true,
            allowGrowX: true,
            allowGrowY: true,
            allowShrinkX: true,
            allowShrinkY: true,
            maxWidth: 32,
            maxHeight: 32
          });
          this._add(control, {
            row: 0,
            column: 0,
            rowSpan: 2
          });
          break;
        case "name":
          control = new qx.ui.basic.Label().set({
            font: "text-14",
            alignY: "middle",
          });
          this._add(control, {
            row: 0,
            column: 1
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __applyThumbnail: function(value) {
      this.getChildControl("thumbnail").setSource(value);
    },

    __applyName: function(value) {
      this.getChildControl("name").setValue(value);
    },

    __applyLeased: function(value) {
      if (value) {
        this.setBackgroundColor("strong-main");
      }
    },

    _onPointerOver: function() {
      this.addState("hovered");
    },

    _onPointerOut : function() {
      this.removeState("hovered");
    },

    _filter: function() {
      this.exclude();
    },

    _unfilter: function() {
      this.show();
    },

    _shouldApplyFilter: function(data) {
      if (data.text) {
        const checks = [
          this.getName(),
        ];
        if (checks.filter(check => check && check.toLowerCase().trim().includes(data.text)).length == 0) {
          return true;
        }
      }
      return false;
    },

    _shouldReactToFilter: function(data) {
      if (data.text && data.text.length > 1) {
        return true;
      }
      return false;
    }
  }
});
