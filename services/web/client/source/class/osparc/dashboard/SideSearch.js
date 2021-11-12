/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

qx.Class.define("osparc.dashboard.SideSearch", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.VBox(6));

    this.set({
      padding: 15,
      marginTop: 15
    });

    this.__buildLayout();
    this.__attachEventHandlers();
  },

  properties: {
    appearance: {
      init: "dashboard",
      refine: true
    }
  },

  members: {
    __textFilter: null,
    __tagsFilter: null,
    __classifierFilter: null,

    __buildLayout: function() {
      const filterGroupId = "sideSearchFilter";
      const title = new qx.ui.basic.Label(this.tr("Filter by")).set({
        font: "text-16"
      });
      this._add(title);

      const textFilter = this.__textFilter = new osparc.component.filter.TextFilter("text", filterGroupId).set({
        allowStretchX: true
      });
      textFilter.getChildControl("textfield").setFont("text-14");
      osparc.utils.Utils.setIdToWidget(textFilter, "sideSearchFiltersTextFld");
      this._add(textFilter);

      const tagsFilter = this.__tagsFilter = new osparc.component.filter.UserTagsFilter("tags", filterGroupId).set({
        visibility: osparc.data.Permissions.getInstance().canDo("study.tag") ? "visible" : "excluded"
      });
      this._add(tagsFilter);

      const classifier = this.__classifierFilter = new osparc.component.filter.ClassifiersFilter("classifiers", filterGroupId).set({
        marginLeft: -12,
        marginTop: -5
      });
      osparc.store.Store.getInstance().addListener("changeClassifiers", () => {
        classifier.recreateTree();
      }, this);
      this._add(classifier, {
        flex: 1
      });
    },

    __attachEventHandlers: function() {
      const textfield = this.__textFilter.getChildControl("textfield");
      textfield.addListener("appear", () => {
        textfield.focus();
      }, this);
    },

    /**
     * Resets the text and active tags.
     */
    reset: function() {
      this.__textFilter.reset();
      this.__tagsFilter.reset();
    },

    /**
     * Returns the text filter widget.
     */
    getTextFilter: function() {
      return this.__textFilter;
    }
  }
});
