/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.component.filter.group.Cucumbar", {
  extend: qx.ui.core.Widget,

  construct: function(filterGroupId) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox());
    this.__groupId = filterGroupId;
    this._layout();
    this._render();
    this._attachEventHandlers();
  },

  properties: {
    appearance: {
      refine: true,
      init: "cucumbar"
    }
  },

  members: {
    __groupId: null,
    __filtersContainer: null,
    __filterControls: null,
    __filterState: null,
    __actionsContainer: null,
    __saveBtn: null,
    __loadBtn: null,
    __clearBtn: null,

    _layout: function() {
      // Bar's left side
      this.__filtersContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      // List of available filters
      this.__filterControls = new qx.ui.container.Composite(new qx.ui.layout.Flow(5,2).set({
        alignY: "middle"
      }));
      this.__filtersContainer.add(this.__filterControls);
      // Human readable filters' state
      this.__filterState = new qx.ui.container.Composite(new qx.ui.layout.Basic());
      this.__filtersContainer.add(this.__filterState);
      // Right side buttons
      this.__actionsContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      this._add(this.__filtersContainer, {
        flex: 1
      });
      this._add(this.__actionsContainer);
      // Filter read
      this.__filterRead = new qx.ui.basic.Label(this.tr("Displaying all items."));
      this.__filterState.add(this.__filterRead);
    },

    _render: function() {
      this.__filterControls.add(new qx.ui.basic.Label("Filter by").set({
        font: "title-16"
      }));
      this.__filterControls.add(new osparc.component.filter.NodeTypeFilter("nodeType", this.__groupId).set({
        tagsVisibility: "excluded"
      }));
      this.__saveBtn = new osparc.ui.form.FetchButton(this.tr("Save")).set({
        appearance: "link-button"
      });
      this.__loadBtn = new osparc.ui.form.FetchButton(this.tr("Load")).set({
        appearance: "link-button"
      });
      this.__clearBtn = new osparc.ui.form.FetchButton(this.tr("Clear all")).set({
        appearance: "link-button"
      });
      this.__actionsContainer.add(this.__saveBtn);
      this.__actionsContainer.add(this.__loadBtn);
      this.__actionsContainer.add(this.__clearBtn);
    },

    __toNaturalLanguage: function(filters) {
      let text = this.tr("Displaying all items.");
      if (Object.keys(filters).length) {
        if (Object.prototype.hasOwnProperty.call(filters, "nodeType") && filters.nodeType.length) {
          text = `Displaying items of type ${filters.nodeType.join(", ")}.`;
        }
      }
      return text;
    },

    _attachEventHandlers: function() {
      const msgName = osparc.utils.Utils.capitalize(this.__groupId, "filter");
      qx.event.message.Bus.getInstance().subscribe(msgName, msg => {
        this.__filterRead.setValue(this.__toNaturalLanguage(msg.getData()));
      }, this);
      this.__clearBtn.addListener("execute", () => {
        osparc.component.filter.UIFilterController.resetGroup(this.__groupId);
      });
    }
  }
});
