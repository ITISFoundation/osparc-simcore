/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.SearchBarFilter", {
  extend: osparc.component.filter.UIFilter,

  construct: function(resourceType) {
    const filterId = resourceType ? "searchBarFilter-"+resourceType : "searchBarFilter";
    const filterGroupId = "searchBarFilter";

    this.base(arguments, filterId, filterGroupId);

    if (resourceType) {
      this.set({
        resourceType
      });
    }

    this._setLayout(new qx.ui.layout.HBox(5));

    this.set({
      backgroundColor: "background-main-2",
      paddingLeft: 6,
      height: 36
    });
    this.getContentElement().setStyles({
      "border-radius": "8px"
    });

    this.__buildLayout();

    this.__buildFiltersMenu();

    this.__attachEventHandlers();
  },

  properties: {
    resourceType: {
      check: ["study", "template", "service"],
      init: null,
      nullable: false
    },

    currentFolder: {
      check: "Number",
      init: null,
      nullable: true,
      event: "changeCurrentFolder",
      apply: "__applyCurrentFolder"
    }
  },

  members: {
    __filtersMenu: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "home-button": {
          control = new qx.ui.toolbar.Button(null, "@FontAwesome5Solid/home/16");
          control.addListener("execute", () => this.setCurrentFolder(null), this);
          this._add(control);
          break;
        }
        case "current-folder-chip": {
          control = new qx.ui.basic.Atom().set({
            icon: "@FontAwesome5Solid/folder/16",
            alignY: "middle"
          });
          this._add(control);
          break;
        }
        case "search-icon":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/search/16").set({
            backgroundColor: "transparent",
            alignY: "middle",
            opacity: 0.5
          });
          this._add(control);
          break;
        case "active-filters":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(4));
          this._add(control);
          break;
        case "text-field":
          control = new qx.ui.form.TextField().set({
            backgroundColor: "background-main-2",
            font: "text-16",
            placeholder: this.tr("search"),
            alignY: "bottom",
            marginBottom: 4
          });
          this._add(control, {
            flex: 1
          });
          break;
        case "reset-button":
          control = new qx.ui.toolbar.Button(null, "@MaterialIcons/close/12").set({
            backgroundColor: "transparent",
            paddingLeft: 0,
            paddingRight: 0,
            alignY: "middle",
            opacity: 0.7
          });
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      if (this.getResourceType() === "study") {
        this.getChildControl("home-button");
        this.setCurrentFolder(null);
      }
      this.getChildControl("search-icon");
      this.getChildControl("active-filters");
      this.getChildControl("text-field");
      this.getChildControl("reset-button");
    },

    __applyCurrentFolder: function(folderId) {
      const currentFolder = this.getChildControl("current-folder-chip");
      currentFolder.setVisibility(folderId ? "visible" : "excluded");

      if (folderId) {
        const folders = osparc.store.Store.getInstance().getFolders();
        const folderFound = folders.find(folder => folder.id === folderId);
        if (folderFound) {
          currentFolder.setLabel(folderFound.name);
          currentFolder.getChildControl("icon").setTextColor(folderFound.color);
        }
      } else {
        this.__removeFolder();
      }
    },

    __buildFiltersMenu: function() {
      if (this.__filtersMenu === null) {
        this.__filtersMenu = new qx.ui.menu.Menu();
      }
      const menu = this.__filtersMenu;
      menu.removeAll();
      const tagsButton = new qx.ui.menu.Button(this.tr("Tags"), "@FontAwesome5Solid/tags/12");
      osparc.utils.Utils.setIdToWidget(tagsButton, "searchBarFilter-tags-button");
      this.__addTags(tagsButton);
      menu.add(tagsButton);

      const classifiersButton = new qx.ui.menu.Button(this.tr("Classifiers"), "@FontAwesome5Solid/search/12");
      osparc.utils.Utils.setIdToWidget(classifiersButton, "searchBarFilter-classifiers");
      this.__addClassifiers(classifiersButton);
      menu.add(classifiersButton);
    },

    __attachEventHandlers: function() {
      const textField = this.getChildControl("text-field");
      textField.addListener("tap", () => this.__showFilterMenu(), this);
      textField.addListener("deactivate", () => this.__hideFilterMenu(), this);
      textField.addListener("keypress", e => {
        if (e.getKeyIdentifier() === "Enter") {
          this.filter();
        } else {
          this.__hideFilterMenu();
        }
      }, this);
      textField.addListener("changeValue", () => this.filter(), this);

      const resetButton = this.getChildControl("reset-button");
      resetButton.addListener("execute", () => this.__resetFilters(), this);

      osparc.store.Store.getInstance().addListener("changeTags", () => this.__buildFiltersMenu(), this);
    },

    __showFilterMenu: function() {
      const textField = this.getChildControl("text-field");
      const textValue = textField.getValue();
      if (textValue) {
        return;
      }

      const element = textField.getContentElement().getDomElement();
      const {
        top,
        left
      } = qx.bom.element.Location.get(element);
      this.__filtersMenu.setLayoutProperties({
        top: top + 30,
        left: left
      });

      this.__filtersMenu.show();
    },

    __hideFilterMenu: function() {
      this.__filtersMenu.exclude();
    },

    __addTags: function(menuButton) {
      const tags = osparc.store.Store.getInstance().getTags();
      menuButton.setVisibility(tags.length ? "visible" : "excluded");
      if (tags.length) {
        const tagsMenu = new qx.ui.menu.Menu();
        osparc.utils.Utils.setIdToWidget(tagsMenu, "searchBarFilter-tags-menu");
        tags.forEach(tag => {
          const tagButton = new qx.ui.menu.Button(tag.name, "@FontAwesome5Solid/tag/12");
          tagButton.getChildControl("icon").setTextColor(tag.color);
          tagsMenu.add(tagButton);
          tagButton.addListener("execute", () => this.addChip("tag", tag.id, tag.name), this);
        });
        menuButton.setMenu(tagsMenu);
      }
    },

    __addClassifiers: function(menuButton) {
      const classifiers = osparc.store.Store.getInstance().getClassifiers();
      menuButton.setVisibility(classifiers.length ? "visible" : "excluded");
      if (classifiers.length) {
        const classifiersMenu = new qx.ui.menu.Menu();
        classifiers.forEach(classifier => {
          const classifierButton = new qx.ui.menu.Button(classifier.display_name);
          classifiersMenu.add(classifierButton);
          classifierButton.addListener("execute", () => this.addChip("classifier", classifier.classifier, classifier.display_name), this);
        });
        menuButton.setMenu(classifiersMenu);
      }
    },

    __createChip: function(chipType, chipId, chipLabel) {
      const chipButton = new qx.ui.form.Button().set({
        label: osparc.utils.Utils.capitalize(chipType) + " = '" + chipLabel + "'",
        icon: "@MaterialIcons/close/12",
        iconPosition: "right",
        paddingRight: 4,
        paddingLeft: 4,
        alignY: "middle",
        toolTipText: chipLabel || "",
        maxHeight: 26,
        maxWidth: 180
      });
      chipButton.type = chipType;
      chipButton.id = chipId;
      chipButton.getContentElement().setStyles({
        "border-radius": "4px"
      });
      chipButton.addListener("execute", () => this.__removeChip(chipType, chipId), this);
      return chipButton;
    },

    addChip: function(type, id, label) {
      const activeFilter = this.getChildControl("active-filters");
      const chipFound = activeFilter.getChildren().find(chip => chip.type === type && chip.id === id);
      if (chipFound) {
        return;
      }
      if (label === undefined) {
        switch (type) {
          case "classifier": {
            const classifierFound = osparc.store.Store.getInstance().getClassifiers().find(classifier => classifier.classfiier === id);
            if (classifierFound) {
              label = classifierFound.display_name;
            }
            break;
          }
          case "tag": {
            const tagFound = osparc.store.Store.getInstance().getTags().find(tag => tag.id === id);
            if (tagFound) {
              label = tagFound.name;
            }
            break;
          }
        }
      }
      const chip = this.__createChip(type, id, label);
      activeFilter.add(chip);
      if (type === "folder") {
        chip.exclude();
        this.setCurrentFolder(id);
      }
      this.filter();
    },

    __removeChip: function(type, id) {
      const activeFilter = this.getChildControl("active-filters");
      const chipFound = activeFilter.getChildren().find(chip => chip.type === type && chip.id === id);
      if (chipFound) {
        activeFilter.remove(chipFound);
        this.filter();
      }
    },

    __removeFolder: function() {
      const activeFilter = this.getChildControl("active-filters");
      const chipFound = activeFilter.getChildren().find(chip => chip.type === "folder");
      if (chipFound) {
        activeFilter.remove(chipFound);
        this.filter();
      }
    },

    __resetFilters: function() {
      this.setCurrentFolder(null);
      this.getChildControl("active-filters").removeAll();
      this.getChildControl("text-field").resetValue();
      this.filter();
    },

    filter: function() {
      const filterData = {
        tags: [],
        classifiers: [],
        folder: null,
        text: this.getChildControl("text-field").getValue() ? this.getChildControl("text-field").getValue() : ""
      };
      this.getChildControl("active-filters").getChildren().forEach(chip => {
        switch (chip.type) {
          case "tag":
            filterData.tags.push(chip.id);
            break;
          case "classifier":
            filterData.classifiers.push(chip.id);
            break;
          case "folder":
            filterData.folder = chip.id;
            break;
        }
      });
      this._filterChange(filterData);
    }
  }
});
