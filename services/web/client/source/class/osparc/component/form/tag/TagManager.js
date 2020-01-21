/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Tag manager server to manage one resource's related tags.
 */
qx.Class.define("osparc.component.form.tag.TagManager", {
  extend: osparc.ui.window.SingletonWindow,
  construct: function(selectedTags, attachment, resourceName, resourceId) {
    this.base(arguments, "tagManager", this.tr("Apply tags to this element"));
    this.set({
      layout: new qx.ui.layout.VBox(),
      allowMinimize: false,
      allowMaximize: false,
      showMinimize: false,
      showMaximize: false,
      autoDestroy: true,
      movable: false,
      resizable: false,
      modal: true,
      appearance: "service-window",
      height: 350,
      width: 262,
      contentPadding: 0
    });
    this.__attachment = attachment;
    this.__resourceName = resourceName;
    this.__resourceId = resourceId;
    this.__selectedTags = new qx.data.Array(selectedTags);
    this.__renderLayout();
    this.__attachEventHandlers();
    this.open();
  },
  events: {
    changeSelected: "qx.event.type.Data"
  },
  properties: {
    liveUpdate: {
      check: "Boolean",
      init: true
    }
  },
  members: {
    __attachment: null,
    __resourceName: null,
    __resourceId: null,
    __selectedTags: null,
    __renderLayout: function() {
      const filterBar = new qx.ui.toolbar.ToolBar();
      const part = new qx.ui.toolbar.Part();
      part.add(new osparc.component.filter.TextFilter("name", "tags"));
      filterBar.add(part);
      this.add(filterBar);
      const buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      this.add(buttonContainer, {
        flex: 1
      });
      osparc.data.Resources.get("tags")
        .then(tags => tags.forEach(tag => buttonContainer.add(this.__tagButton(tag))))
        .catch(console.err);
    },
    /**
     * If the attachment (element close to which the TagManager is being rendered) is already on the DOM,
     * this function calculates where the TagManager should render, taking into account the window edges.
     */
    __updatePosition: function() {
      if (this.__attachment && this.__attachment.getContentElement().getDomElement()) {
        const location = qx.bom.element.Location.get(this.__attachment.getContentElement().getDomElement());
        const freeDistances = osparc.utils.Utils.getFreeDistanceToWindowEdges(this.__attachment);
        let position = {
          top: location.bottom,
          left: location.right
        };
        if (this.getWidth() > freeDistances.right) {
          position.left = location.left - this.getWidth();
          if (this.getHeight() > freeDistances.bottom) {
            position.top = location.top - this.getHeight();
          }
        } else if (this.getHeight() > freeDistances.bottom) {
          position.top = location.top - this.getHeight();
        }
        this.moveTo(position.left, position.top);
      } else {
        this.center();
      }
    },
    __tagButton: function(tag) {
      const button = new osparc.component.form.tag.TagToggleButton(tag).set({
        value: this.__selectedTags.includes(tag.id)
      });
      button.addListener("changeValue", evt => {
        const selected = evt.getData();
        if (this.isLiveUpdate()) {
          button.setFetching(true);
          const params = {
            url: {
              tagId: tag.id,
              studyUuid: this.__resourceId
            }
          };
          if (selected) {
            osparc.data.Resources.fetch("studies", "addTag", params)
              .then(() => this.__selectedTags.push(tag.id))
              .catch(err => {
                console.error(err);
                button.setValue(false);
              })
              .finally(() => button.setFetching(false));
          } else {
            osparc.data.Resources.fetch("studies", "removeTag", params)
              .then(() => this.__selectedTags.remove(tag.id))
              .catch(err => {
                console.error(err);
                button.setValue(true);
              })
              .finally(() => button.setFetching(false));
          }
        } else {
          if (selected) {
            this.__selectedTags.push(tag.id)
          } else {
            this.__selectedTags.remove(tag.id)
          }
        }
      }, this);
      return button;
    },
    __attachEventHandlers: function() {
      this.addListener("appear", () => this.__updatePosition(), this);
      this.__selectedTags.addListener("change", evt => {
        this.fireDataEvent("changeSelected", {
          ...evt.getData(),
          selected: this.__selectedTags.toArray()
        });
      }, this);
    }
  }
});
