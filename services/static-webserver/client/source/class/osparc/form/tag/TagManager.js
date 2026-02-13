/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

/**
 * Tag manager server to manage one resource's related tags.
 */
qx.Class.define("osparc.form.tag.TagManager", {
  extend: qx.ui.core.Widget,

  construct: function(studyData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.__selectedTags = new qx.data.Array();
    this.__renderLayout();
    this.__attachEventHandlers();

    this.setStudyData(studyData);
  },

  events: {
    "updateTags": "qx.event.type.Data",
    "changeSelected": "qx.event.type.Data",
    "selectedTags": "qx.event.type.Data",
  },

  properties: {
    liveUpdate: {
      check: "Boolean",
      event: "changeLiveUpdate",
      init: false
    }
  },

  statics: {
    popUpInWindow: function(tagManager, title) {
      if (!title) {
        title = qx.locale.Manager.tr("Apply Tags");
      }
      const width = 400;
      const maxHeight = 500;
      return osparc.ui.window.Window.popUpInWindow(tagManager, title, width).set({
        allowMinimize: false,
        allowMaximize: false,
        showMinimize: false,
        showMaximize: false,
        clickAwayClose: true,
        movable: true,
        resizable: true,
        showClose: true,
        maxHeight,
      });
    }
  },

  members: {
    __studyData: null,
    __resourceId: null,
    __introLabel: null,
    __selectedTags: null,
    __tagsContainer: null,
    __addTagButton: null,

    _createChildControlImpl: function(id, hash) {
      let control;
      switch (id) {
        case "buttons-container":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
            alignX: "right"
          }));
          this._add(control);
          break;
        case "save-button":
          control = new osparc.ui.form.FetchButton(this.tr("Save")).set({
            appearance: "strong-button"
          });
          osparc.utils.Utils.setIdToWidget(control, "saveTagsBtn");
          control.addListener("execute", () => this.__save(control), this);
          this.getChildControl("buttons-container").add(control);
          break;
        case "ok-button":
          control = new osparc.ui.form.FetchButton(this.tr("Save")).set({
            appearance: "strong-button"
          });
          control.addListener("execute", () => this.__okClicked(control), this);
          this.getChildControl("buttons-container").add(control);
          break;
      }
      return control || null;
    },

    __renderLayout: function() {
      const introLabel = this.__introLabel = osparc.dashboard.ResourceDetails.createIntroLabel();
      this._add(introLabel);

      const filter = new osparc.filter.TextFilter("name", "studyBrowserTagManager").set({
        allowStretchX: true,
        margin: [0, 10, 5, 10]
      });
      this._add(filter);

      const tagsContainer = this.__tagsContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      const scrollTags = new qx.ui.container.Scroll();
      scrollTags.add(tagsContainer);
      this._add(scrollTags, {
        flex: 1
      });

      const addTagButton = this.__addTagButton = new qx.ui.form.Button().set({
        appearance: "form-button-outlined",
        label: this.tr("New Tag"),
        icon: "@FontAwesome5Solid/plus/14",
        alignX: "center",
        allowGrowX: false,
        marginTop: 10,
      });
      addTagButton.addListener("execute", () => {
        this.__repopulateTags();
        const newItem = new osparc.form.tag.TagItem().set({
          mode: osparc.form.tag.TagItem.modes.EDIT
        });
        newItem.addListener("tagSaved", () => this.__repopulateTags(), this);
        newItem.addListener("cancelNewTag", e => tagsContainer.remove(e.getTarget()), this);
        newItem.addListener("deleteTag", e => tagsContainer.remove(e.getTarget()), this);
        tagsContainer.add(newItem);

        // scroll down
        const height = scrollTags.getSizeHint().height;
        scrollTags.scrollToY(height);
      });
      this._add(addTagButton);

      const buttons = this.getChildControl("buttons-container");
      this.bind("liveUpdate", buttons, "visibility", {
        converter: value => value ? "excluded" : "visible"
      });
      this.getChildControl("save-button");
    },

    setStudyData: function(studyData) {
      this.__studyData = studyData;
      this.__resourceId = studyData["uuid"];

      const resourceAlias = osparc.product.Utils.resourceTypeToAlias(this.__studyData["resourceType"], {plural: true}) || "projects";
      this.__introLabel.set({
        value: this.tr("Manage and apply tags to better organize your " + resourceAlias + ". Select from existing tags or create new ones, then save your changes when ready."),
      });

      this.__selectedTags.removeAll();
      this.__selectedTags.append(studyData["tags"]);
      this.__repopulateTags();
    },

    __repopulateTags: function() {
      this.__tagsContainer.removeAll();
      const tags = osparc.store.Tags.getInstance().getTags();
      const tagButtons = [];
      tags.forEach(tag => tagButtons.push(this.__tagButton(tag)));
      // list the selected tags first
      tagButtons.sort((a, b) => b.getValue() - a.getValue());
      tagButtons.forEach(tagButton => this.__tagsContainer.add(tagButton));
    },

    __tagButton: function(tag) {
      const tagId = tag.getTagId();
      const tagButton = new osparc.form.tag.TagToggleButton(tag, this.__selectedTags.includes(tagId));
      tagButton.addListener("changeValue", evt => {
        const selected = evt.getData();
        if (this.isLiveUpdate()) {
          tagButton.setFetching(true);
          if (selected) {
            this.__saveAddTag(tagId, tagButton)
              .then(updatedStudy => {
                if (updatedStudy) {
                  this.fireDataEvent("updateTags", updatedStudy);
                }
              });
          } else {
            this.__saveRemoveTag(tagId, tagButton)
              .then(updatedStudy => {
                if (updatedStudy) {
                  this.fireDataEvent("updateTags", updatedStudy);
                }
              });
          }
        } else if (selected) {
          this.__selectedTags.push(tagId);
        } else {
          this.__selectedTags.remove(tagId);
        }
      }, this);
      tagButton.subscribeToFilterGroup("studyBrowserTagManager");
      return tagButton;
    },

    __saveAddTag: function(tagId, tagButton) {
      return osparc.store.Study.getInstance().addTag(this.__resourceId, tagId)
        .then(updatedStudy => {
          this.__selectedTags.push(tagId);
          return updatedStudy;
        })
        .catch(() => tagButton ? tagButton.setValue(false) : null)
        .finally(() => tagButton ? tagButton.setFetching(false) : null);
    },

    __saveRemoveTag: function(tagId, tagButton) {
      return osparc.store.Study.getInstance().removeTag(this.__resourceId, tagId)
        .then(updatedStudy => {
          this.__selectedTags.remove(tagId);
          return updatedStudy;
        })
        .catch(() => tagButton ? tagButton.setValue(true) : null)
        .finally(() => tagButton ? tagButton.setFetching(false) : null);
    },

    __save: async function(saveButton) {
      saveButton.setFetching(true);

      // call them sequentially
      let updatedStudy = null;
      for (let i=0; i<this.__selectedTags.length; i++) {
        const tagId = this.__selectedTags.getItem(i);
        if (!this.__studyData["tags"].includes(tagId)) {
          updatedStudy = await this.__saveAddTag(tagId);
        }
      }
      for (let i=0; i<this.__studyData["tags"].length; i++) {
        const tagId = this.__studyData["tags"][i];
        if (!this.__selectedTags.includes(tagId)) {
          updatedStudy = await this.__saveRemoveTag(tagId);
        }
      }

      saveButton.setFetching(false);
      if (updatedStudy) {
        this.fireDataEvent("updateTags", updatedStudy);
      }
    },

    __okClicked: function() {
      this.fireDataEvent("selectedTags", {
        tags: this.__selectedTags.toArray(),
      });
    },

    __attachEventHandlers: function() {
      this.__selectedTags.addListener("change", evt => {
        this.fireDataEvent("changeSelected", {
          ...evt.getData(),
          selected: this.__selectedTags.toArray()
        });
      }, this);
    }
  }
});
