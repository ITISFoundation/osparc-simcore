/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* eslint "qx-rules/no-refs-in-members": "warn" */

/**
 * Widget used mainly by ServiceBrowser for displaying service related information
 *
 *   It consists of a key as title, and name and contact as caption
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   tree.setDelegate({
 *     createItem: () => new qxapp.desktop.ServiceBrowserListItem(),
 *     bindItem: (c, item, id) => {
 *       c.bindProperty("key", "model", null, item, id);
 *       c.bindProperty("key", "title", null, item, id);
 *       c.bindProperty("name", "name", null, item, id);
 *       c.bindProperty("type", "type", null, item, id);
 *       c.bindProperty("category", "category", null, item, id);
 *       c.bindProperty("contact", "contact", null, item, id);
 *     }
 *   });
 * </pre>
 */

qx.Class.define("qxapp.desktop.ServiceBrowserListItem", {
  extend: qx.ui.core.Widget,
  implement : [qx.ui.form.IModel, qxapp.component.filter.IFilterable],
  include : [qx.ui.form.MModelProperty, qxapp.component.filter.MFilterable],

  construct: function() {
    this.base(arguments);

    let layout = new qx.ui.layout.VBox(5).set({
      alignY: "middle"
    });
    this._setLayout(layout);

    this._add(this.getChildControl("title"));
    this._add(this.getChildControl("subtitle"));

    this.addListener("pointerover", this._onPointerOver, this);
    this.addListener("pointerout", this._onPointerOut, this);
  },

  events:
  {
    /** (Fired by {@link qx.ui.form.List}) */
    "action" : "qx.event.type.Event"
  },

  properties: {
    appearance: {
      refine : true,
      init : "pb-listitem"
    },

    title: {
      check : "String",
      apply : "_applyTitle",
      nullable : true
    },

    name: {
      check : "String",
      apply : "_applyName",
      nullable : true
    },

    type: {
      check : "String",
      apply : "_applyType",
      nullable : true
    },

    contact: {
      check : "String",
      apply : "_applyContact",
      nullable : true
    },

    category: {
      check : "String",
      nullable : true
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
        case "title":
          control = new qxapp.ui.basic.Label(14, true);
          break;
        case "subtitle":
          control = new qx.ui.basic.Label();
          break;
      }

      return control || this.base(arguments, id);
    },

    _applyTitle: function(value) {
      let label = this.getChildControl("title");
      label.setValue(value);
    },

    _applyName: function(value) {
      this.setName(value);
      this.__updateSubtitle();
    },

    _applyType: function(value) {
      this.setType(value);
      this.__updateSubtitle();
    },

    _applyContact: function(value) {
      this.setContact(value);
      this.__updateSubtitle();
    },

    __updateSubtitle: function() {
      let subtitle = this.getChildControl("subtitle");
      let textToShow = "Name: ";
      textToShow += this.getName();
      textToShow += ", Contact: ";
      textToShow += this.getContact();
      subtitle.setValue(textToShow);
    },

    _filter: function() {
      this.exclude();
    },

    _unfilter: function() {
      this.show();
    },

    _shouldApplyFilter: function(data) {
      if (data.text) {
        const label = this.getName()
          .trim()
          .toLowerCase();
        if (label.indexOf(data.text) === -1) {
          return true;
        }
      }
      if (data.tags && data.tags.length) {
        const category = this.getCategory() || "";
        const type = this.getType() || "";
        if (!data.tags.includes(category.trim().toLowerCase()) && !data.tags.includes(type.trim().toLowerCase())) {
          return true;
        }
      }
      return false;
    },

    _shouldReactToFilter: function(data) {
      if (data.text && data.text.length > 1) {
        return true;
      }
      if (data.tags && data.tags.length) {
        return true;
      }
      return false;
    }
  }
});
