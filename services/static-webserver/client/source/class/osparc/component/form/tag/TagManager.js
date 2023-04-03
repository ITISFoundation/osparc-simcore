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
qx.Class.define("osparc.component.form.tag.TagManager", {
  extend: qx.ui.core.Widget,

  construct: function(studyData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.__studyData = studyData;
    this.__resourceId = studyData["uuid"];
    this.__selectedTags = new qx.data.Array(studyData["tags"]);

    this.__renderLayout();
    this.__attachEventHandlers();
  },

  events: {
    "updateTags": "qx.event.type.Data",
    "changeSelected": "qx.event.type.Data"
  },

  properties: {
    liveUpdate: {
      check: "Boolean",
      event: "changeLiveUpdate",
      init: true
    }
  },

  statics: {
    popUpInWindow: function(tagManager, title) {
      if (!title) {
        title = qx.locale.Manager.tr("Apply Tags");
      }
      return osparc.ui.window.Window.popUpInWindow(tagManager, title, 280, null).set({
        allowMinimize: false,
        allowMaximize: false,
        showMinimize: false,
        showMaximize: false,
        clickAwayClose: true,
        movable: true,
        resizable: true,
        showClose: true
      });
    }
  },

  members: {
    __studyData: null,
    __attachment: null,
    __resourceName: null,
    __resourceId: null,
    __selectedTags: null,

    __renderLayout: function() {
      const filter = new osparc.component.filter.TextFilter("name", "studyBrowserTagManager").set({
        allowStretchX: true,
        margin: [0, 10, 5, 10]
      });
      this._add(filter);

      const buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      this._add(buttonContainer, {
        flex: 1
      });
      osparc.store.Store.getInstance().getTags().forEach(tag => buttonContainer.add(this.__tagButton(tag)));
      if (buttonContainer.getChildren().length === 0) {
        buttonContainer.add(new qx.ui.basic.Label().set({
          value: this.tr("Add your first tag in Preferences/Tags"),
          font: "title-16",
          textColor: "service-window-hint",
          rich: true,
          padding: 10,
          textAlign: "center"
        }));
      }

      const buttons = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignX: "right"
      }));
      const saveButton = new osparc.ui.form.FetchButton(this.tr("Save"));
      osparc.utils.Utils.setIdToWidget(saveButton, "saveTagsBtn");
      saveButton.addListener("execute", e => {
        this.__save(saveButton);
      }, this);
      buttons.add(saveButton);
      this.bind("liveUpdate", buttons, "visibility", {
        converter: value => value ? "excluded" : "visible"
      });
      this._add(buttons);
    },

    __tagButton: function(tag) {
      const tagButton = new osparc.component.form.tag.TagToggleButton(tag, this.__selectedTags.includes(tag.id));
      tagButton.addListener("changeValue", evt => {
        const selected = evt.getData();
        if (this.isLiveUpdate()) {
          tagButton.setFetching(true);
          if (selected) {
            this.__saveAddTag(tag.id, tagButton);
          } else {
            this.__saveRemoveTag(tag.id, tagButton);
          }
        } else if (selected) {
          this.__selectedTags.push(tag.id);
        } else {
          this.__selectedTags.remove(tag.id);
        }
      }, this);
      tagButton.subscribeToFilterGroup("studyBrowserTagManager");
      return tagButton;
    },

    __getAddTagPromise: function(tagId) {
      const params = {
        url: {
          tagId,
          studyId: this.__resourceId
        }
      };
      return osparc.data.Resources.fetch("studies", "addTag", params);
    },

    __getRemoveTagPromise: function(tagId) {
      const params = {
        url: {
          tagId,
          studyId: this.__resourceId
        }
      };
      return osparc.data.Resources.fetch("studies", "removeTag", params);
    },

    __saveAddTag: function(tagId, tagButton) {
      this.__getAddTagPromise(tagId)
        .then(() => this.__selectedTags.push(tagId))
        .catch(err => {
          console.error(err);
          tagButton.setValue(false);
        })
        .finally(() => tagButton.setFetching(false));
    },

    __saveRemoveTag: function(tagId, tagButton) {
      this.__getRemoveTagPromise(tagId)
        .then(() => this.__selectedTags.remove(tagId))
        .catch(err => {
          console.error(err);
          tagButton.setValue(true);
        })
        .finally(() => tagButton.setFetching(false));
    },

    __save: async function(saveButton) {
      saveButton.setFetching(true);

      // call them sequentially
      let updatedStudy = null;
      for (let i=0; i<this.__selectedTags.length; i++) {
        const tagId = this.__selectedTags.getItem(i);
        if (!this.__studyData["tags"].includes(tagId)) {
          updatedStudy = await this.__getAddTagPromise(tagId)
            .then(updatedData => updatedData);
        }
      }
      for (let i=0; i<this.__studyData["tags"].length; i++) {
        const tagId = this.__studyData["tags"][i];
        if (!this.__selectedTags.includes(tagId)) {
          updatedStudy = await this.__getRemoveTagPromise(tagId)
            .then(updatedData => updatedData);
        }
      }

      saveButton.setFetching(false);
      if (updatedStudy) {
        this.fireDataEvent("updateTags", updatedStudy);
      }
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
