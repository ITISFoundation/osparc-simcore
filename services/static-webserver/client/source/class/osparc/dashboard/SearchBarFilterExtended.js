/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.SearchBarFilterExtended", {
  extend: qx.ui.core.Widget,

  construct: function(resourceType, initFilterData = {}) {
    this.base(arguments, "searchBarFilter-"+resourceType, "searchBarFilter");

    this._setLayout(new qx.ui.layout.VBox(10));

    this.set({
      backgroundColor: osparc.dashboard.SearchBarFilter.BG_COLOR,
      padding: 8,
      decorator: "rounded",
    });
    osparc.utils.Utils.addBorder(this, 1, qx.theme.manager.Color.getInstance().resolve("product-color"));

    this.__resourceType = resourceType;
    this.__initFilterData = initFilterData;

    this.__buildLayout();

    this.setCurrentContext(osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_PROJECTS);

    qx.core.Init.getApplication().getRoot().add(this);

    this.__attachHideHandlers();
  },

  events: {
    "filterChanged": "qx.event.type.Data",
    "resetButtonPressed": "qx.event.type.Event",
  },

  properties: {
    currentContext: {
      check: [
        "searchProjects",        // osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_PROJECTS,
        "searchTemplates",       // osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_TEMPLATES,
        "searchPublicTemplates", // osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_PUBLIC_TEMPLATES,
        "searchFunctions",       // osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_FUNCTIONS,
        "searchFiles",           // osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_FILES,
      ],
      init: null,
      nullable: false,
      event: "changeCurrentContext",
      apply: "__applyCurrentContext",
    },
  },

  statics: {
    decorateListItem: function(listItem) {
      listItem.set({
        gap: 8,
        backgroundColor: osparc.dashboard.SearchBarFilter.BG_COLOR,
      });
    },

    createListItem: function(label, icon, model) {
      const listItem = new qx.ui.form.ListItem(label, icon, model);
      this.self().decorateListItem(listItem);
      return listItem;
    },
  },

  members: {
    __resourceType: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "search-bar-filter": {
          control = new osparc.dashboard.SearchBarFilter(this.__resourceType).set({
            showFilterMenu: false,
          });
          const textField = control.getChildControl("text-field");
          textField.addListener("appear", () => {
            textField.focus();
            textField.activate();
          });
          const resetButton = control.getChildControl("reset-button");
          resetButton.set({
            paddingRight: 2, // 10-8
            opacity: 0.7,
            backgroundColor: "transparent",
          });
          osparc.utils.Utils.hideBorder(resetButton);
          this._add(control);
          break;
        }
        case "context-drop-down": {
          control = new qx.ui.form.SelectBox().set({
            minWidth: 150,
          });
          control.getChildControl("arrow").syncAppearance(); // force sync to show the arrow
          this.self().decorateListItem(control.getChildControl("atom"));
          const searchBarFilter = this.getChildControl("search-bar-filter");
          searchBarFilter._addAt(control, 3); //"search-icon", "active-filters", "text-field", "reset-button"
          break;
        }
        case "my-projects-button": {
          control = this.self().createListItem(
            this.tr("My Projects"),
            "@FontAwesome5Solid/file/14",
            "myProjects"
          );
          const contextDropDown = this.getChildControl("context-drop-down");
          contextDropDown.add(control);
          break;
        }
        case "templates-button": {
          control = this.self().createListItem(
            this.tr("Templates"),
            "@FontAwesome5Solid/copy/14",
            "templates"
          );
          const contextDropDown = this.getChildControl("context-drop-down");
          contextDropDown.add(control);
          break;
        }
        case "public-projects-button": {
          control = this.self().createListItem(
            this.tr("Public Projects"),
            "@FontAwesome5Solid/globe/14",
            "publicProjects"
          );
          const contextDropDown = this.getChildControl("context-drop-down");
          contextDropDown.add(control);
          break;
        }
        case "functions-button": {
          control = this.self().createListItem(
            this.tr("Functions"),
            "@MaterialIcons/functions/16",
            "functions"
          );
          const contextDropDown = this.getChildControl("context-drop-down");
          contextDropDown.add(control);
          break;
        }
        case "files-button": {
          control = this.self().createListItem(
            this.tr("Files"),
            "@FontAwesome5Solid/file-alt/14",
            "files"
          );
          const contextDropDown = this.getChildControl("context-drop-down");
          contextDropDown.add(control);
          break;
        }
        case "filters-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          this._add(control);
          break;
        case "filter-buttons":
          control = new qx.ui.toolbar.ToolBar().set({
            backgroundColor: osparc.dashboard.SearchBarFilter.BG_COLOR,
          });
          this.getChildControl("filters-layout").add(control);
          break;
        case "shared-with-button":
          control = new qx.ui.toolbar.MenuButton(this.tr("Shared with"), "@FontAwesome5Solid/share-alt/12");
          this.__addSharedWithMenu(control);
          this.getChildControl("filter-buttons").add(control);
          break;
        case "tags-button":
          control = new qx.ui.toolbar.MenuButton(this.tr("Tags"), "@FontAwesome5Solid/tags/12");
          this.__addTagsMenu(control);
          this.getChildControl("filter-buttons").add(control);
          break;
        case "date-filters":
          control = new osparc.filter.DateFilters();
          control.addListener("change", e => {
            const dateRange = e.getData();
            this.__filter("modifiedAt", dateRange);
          });
          this.getChildControl("filters-layout").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      const searchBarFilter = this.getChildControl("search-bar-filter");

      const contextDropDown = this.getChildControl("context-drop-down");
      this.getChildControl("my-projects-button");
      if (osparc.product.Utils.showTemplates()) {
        this.getChildControl("templates-button");
      }
      if (osparc.product.Utils.showPublicProjects()) {
        this.getChildControl("public-projects-button");
      }
      if (osparc.product.Utils.showFunctions()) {
        this.getChildControl("functions-button");
      }
      this.getChildControl("files-button");
      if (contextDropDown.getChildren().length === 1) {
        contextDropDown.hide();
      }
      contextDropDown.addListener("changeSelection", e => {
        const selection = e.getData();
        if (selection.length) {
          const selectedContext = selection[0].getModel();
          switch (selectedContext) {
            case "myProjects":
              this.setCurrentContext(osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_PROJECTS);
              break;
            case "templates":
              this.setCurrentContext(osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_TEMPLATES);
              break;
            case "publicProjects":
              this.setCurrentContext(osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_PUBLIC_TEMPLATES);
              break;
            case "functions":
              this.setCurrentContext(osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_FUNCTIONS);
              break;
            case "files":
              this.setCurrentContext(osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_FILES);
              break;
          }
        }
      });

      // Set initial state based on the provided initFilterData
      const activeFilters = searchBarFilter.getChildControl("active-filters");
      const textField = searchBarFilter.getChildControl("text-field");
      if ("sharedWith" in this.__initFilterData && this.__initFilterData["sharedWith"]) {
        const sharedWithOptions = osparc.dashboard.SearchBarFilter.getSharedWithOptions(this.__resourceType);
        const optionsFound = sharedWithOptions.find(option => option.id === this.__initFilterData["sharedWith"]);
        if (optionsFound) {
          const chip = osparc.dashboard.SearchBarFilter.createChip("sharedWith", optionsFound.id, optionsFound.label);
          activeFilters.add(chip);
        }
      }
      if ("tags" in this.__initFilterData && this.__initFilterData["tags"]) {
        const tags = osparc.store.Tags.getInstance().getTags();
        this.__initFilterData["tags"].forEach(tagId => {
          const tagFound = tags.find(tag => tag.getTagId() === tagId);
          if (tagFound) {
            const chip = osparc.dashboard.SearchBarFilter.createChip("tag", tagId, tagFound.getName());
            activeFilters.add(chip);
          }
        });
      }
      if ("text" in this.__initFilterData && this.__initFilterData["text"]) {
        textField.setValue(this.__initFilterData["text"]);
      }

      // Add listeners
      textField.addListener("keypress", e => {
        if (e.getKeyIdentifier() === "Enter") {
          this.__filter("text", textField.getValue());
        }
      }, this);
      textField.addListener("unfocus", () => {
        this.__filter("text", textField.getValue());
      }, this);

      const resetButton = searchBarFilter.getChildControl("reset-button");
      resetButton.addListener("tap", () => {
        this.fireEvent("resetButtonPressed");
        this.exclude();
      });
    },

    __applyCurrentContext: function(value, old) {
      if (value === old) {
        return;
      }
      const contextDropDown = this.getChildControl("context-drop-down");
      const searchBarFilter = this.getChildControl("search-bar-filter");
      const sharedWithButton = this.getChildControl("shared-with-button");
      const tagsButton = this.getChildControl("tags-button");
      const dateFilters = this.getChildControl("date-filters");
      switch (value) {
        case osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_PROJECTS:
          contextDropDown.setSelection([this.getChildControl("my-projects-button")]);
          searchBarFilter.getChildControl("text-field").setPlaceholder(this.tr("Search in My projects"));
          sharedWithButton.show();
          tagsButton.show();
          dateFilters.exclude();
          break;
        case osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_TEMPLATES:
          contextDropDown.setSelection([this.getChildControl("templates-button")]);
          searchBarFilter.getChildControl("text-field").setPlaceholder(this.tr("Search in Templates"));
          sharedWithButton.exclude();
          tagsButton.show();
          dateFilters.exclude();
          break;
        case osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_PUBLIC_TEMPLATES:
          contextDropDown.setSelection([this.getChildControl("public-projects-button")]);
          searchBarFilter.getChildControl("text-field").setPlaceholder(this.tr("Search in Public Projects"));
          sharedWithButton.exclude();
          tagsButton.show();
          dateFilters.exclude();
          break;
        case osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_FUNCTIONS:
          contextDropDown.setSelection([this.getChildControl("functions-button")]);
          searchBarFilter.getChildControl("text-field").setPlaceholder(this.tr("Search in Functions"));
          sharedWithButton.exclude();
          tagsButton.exclude();
          dateFilters.exclude();
          break;
        case osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_FILES:
          contextDropDown.setSelection([this.getChildControl("files-button")]);
          searchBarFilter.getChildControl("text-field").setPlaceholder(this.tr("Search in Files"));
          sharedWithButton.exclude();
          tagsButton.exclude();
          dateFilters.exclude();
          break;
      }
    },

    __filter: function(filterType, filterData) {
      this.fireDataEvent("filterChanged", {
        searchContext: this.getCurrentContext(),
        filterType,
        filterData,
      });
      this.exclude();
    },

    __addSharedWithMenu: function(menuButton) {
      const menu = this.__sharedWithMenu = new qx.ui.menu.Menu();

      const sharedWithRadioGroup = new qx.ui.form.RadioGroup();
      const options = osparc.dashboard.SearchBarFilter.getSharedWithOptions(this.__resourceType);
      options.forEach((option, idx) => {
        const button = new qx.ui.menu.RadioButton(option.label);
        menu.add(button);
        button.addListener("execute", () => this.__filter("sharedWith", option));
        sharedWithRadioGroup.add(button);
        // preselect show-all
        if (idx === 0) {
          sharedWithRadioGroup.setSelection([button]);
        }
      });
      menuButton.setMenu(menu);
    },

    __addTagsMenu: function(menuButton) {
      const tags = osparc.store.Tags.getInstance().getTags();
      menuButton.setVisibility(tags.length ? "visible" : "excluded");
      if (tags.length) {
        const menu = this.__tagsMenu = new qx.ui.menu.Menu();
        osparc.utils.Utils.setIdToWidget(menu, "searchBarFilter-tags-menu");
        tags.forEach(tag => {
          const tagButton = new qx.ui.menu.Button(tag.getName(), "@FontAwesome5Solid/tag/12");
          tagButton.getChildControl("icon").setTextColor(tag.getColor());
          menu.add(tagButton);
          tagButton.addListener("execute", () => this.__filter("tag", tag));
        });
        menuButton.setMenu(menu);
      }
    },

    __attachHideHandlers: function() {
      const tapListener = e => {
        const excludeElements = [
          this,
          this.__sharedWithMenu,
          this.__tagsMenu,
        ];
        // handle clicks on the drop down menu that might go out of bounds
        const contextDropDown = this.getChildControl("context-drop-down");
        const popup = contextDropDown.getChildControl("popup");
        if (popup.isVisible()) {
          excludeElements.push(popup);
        }
        for (let i = 0; i < excludeElements.length; i++) {
          if (excludeElements[i] && osparc.utils.Utils.isMouseOnElement(excludeElements[i], e)) {
            return;
          }
        }

        this.exclude();
        document.removeEventListener("mousedown", tapListener);
      };
      document.addEventListener("mousedown", tapListener);
    },
  }
});
