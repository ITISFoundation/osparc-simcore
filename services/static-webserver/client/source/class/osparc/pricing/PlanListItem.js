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

qx.Class.define("osparc.pricing.PlanListItem", {
  extend: qx.ui.core.Widget,
  implement : [qx.ui.form.IModel, osparc.filter.IFilterable],
  include : [qx.ui.form.MModelProperty, osparc.filter.MFilterable],

  construct: function() {
    this.base(arguments);

    const layout = new qx.ui.layout.Grid(20, 5);
    layout.setColumnFlex(2, 1);
    this._setLayout(layout);
    this.setPadding(10);

    this.getChildControl("title");
    this.getChildControl("description");
    this.getChildControl("classification");
    this.getChildControl("edit-button");

    this.addListener("pointerover", this._onPointerOver, this);
    this.addListener("pointerout", this._onPointerOut, this);
  },

  events: {
    /** (Fired by {@link qx.ui.form.List}) */
    "action": "qx.event.type.Event",
    "editPricingPlan": "qx.event.type.Event"
  },

  properties: {
    appearance: {
      refine: true,
      init: "selectable"
    },

    ppId: {
      check: "Number",
      nullable: true,
      apply: "__applyPpId",
      event: "changePpId"
    },

    ppKey: {
      check: "String",
      apply: "__applyPpKey",
      nullable: true,
      event: "changePpKey"
    },

    title: {
      check: "String",
      nullable: true,
      event: "changeTitle"
    },

    description: {
      check: "String",
      nullable: true,
      event: "changeDescription"
    },

    classification: {
      check: "String",
      nullable: true,
      event: "changeClassification"
    },

    isActive: {
      check: "Boolean",
      apply: "__applyIsActive",
      nullable : true,
      event: "changeIsActive"
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

    /**
     * Event handler for the pointer over event.
     */
    _onPointerOver: function() {
      this.addState("hovered");
    },


    /**
     * Event handler for the pointer out event.
     */
    _onPointerOut : function() {
      this.removeState("hovered");
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "pp-id":
          control = new qx.ui.basic.Label().set({
            font: "text-14",
            alignY: "middle",
          });
          this._add(control, {
            row: 0,
            column: 0,
            rowSpan: 2
          });
          break;
        case "pp-key":
          control = new qx.ui.basic.Label().set({
            font: "text-14",
            alignY: "middle",
          });
          this._add(control, {
            row: 0,
            column: 1,
            rowSpan: 2
          });
          break;
        case "title":
          control = new qx.ui.basic.Label().set({
            font: "text-14"
          });
          this.bind("title", control, "value");
          this._add(control, {
            row: 0,
            column: 2
          });
          break;
        case "description":
          control = new qx.ui.basic.Label().set({
            font: "text-13"
          });
          this.bind("description", control, "value");
          this._add(control, {
            row: 1,
            column: 2
          });
          break;
        case "classification":
          control = new qx.ui.basic.Label().set({
            font: "text-14",
            alignY: "middle",
          });
          this.bind("classification", control, "value");
          this._add(control, {
            row: 0,
            column: 3,
            rowSpan: 2
          });
          break;
        case "is-active":
          control = new qx.ui.basic.Label().set({
            font: "text-14",
            alignY: "middle"
          });
          this._add(control, {
            row: 0,
            column: 4,
            rowSpan: 2
          });
          break;
        case "edit-button":
          control = new qx.ui.form.Button(this.tr("Edit")).set({
            alignY: "middle",
            allowGrowY: false
          });
          control.addListener("tap", () => this.fireEvent("editPricingPlan"));
          this._add(control, {
            row: 0,
            column: 5,
            rowSpan: 2
          });
          break;
      }
      if (control && id !== "edit-button") {
        // make edit button tappable
        control.set({
          anonymous: true
        });
      }

      return control || this.base(arguments, id);
    },

    __applyPpId: function(id) {
      if (id === null) {
        return;
      }
      const label = this.getChildControl("pp-id");
      label.setValue("Id: " + id);
    },

    __applyPpKey: function(id) {
      if (id === null) {
        return;
      }
      const label = this.getChildControl("pp-key");
      label.setValue("Key: " + id);
    },

    __applyIsActive: function(value) {
      if (value === null) {
        return;
      }
      const label = this.getChildControl("is-active");
      label.setValue(value ? "Active" : "Inactive");
    },

    /**
     * Event handler for filtering events.
     */
    _filter: function() {
      this.exclude();
    },

    _unfilter: function() {
      this.show();
    },

    _shouldApplyFilter: function(data) {
      if (data.text) {
        const checks = [
          this.getTitle(),
          this.getDescription()
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
