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
      init: false
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
        .then(tags => tags.forEach(tag => buttonContainer.add(this.__tagButton(tag))));
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
        if (evt.getData()) {
          this.__selectedTags.push(tag.id);
        } else {
          this.__selectedTags.remove(tag.id);
        }
        this.fireDataEvent("changeSelected", this.__selectedTags.toArray());
      }, this);
      return button;
    },
    __attachEventHandlers: function() {
      this.addListener("appear", () => this.__updatePosition(), this);
    }
  }
});
