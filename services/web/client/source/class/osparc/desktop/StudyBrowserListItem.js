/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Tobias Oetiker (oetiker)

************************************************************************ */

/* eslint "qx-rules/no-refs-in-members": "warn" */

/**
 * Widget used mainly by StudyBrowser for displaying Studies
 *
 * It consists of a thumbnail and creator and last change as caption
 */

qx.Class.define("osparc.desktop.StudyBrowserListItem", {
  extend: qx.ui.form.ToggleButton,
  implement : [qx.ui.form.IModel, osparc.component.filter.IFilterable],
  include : [qx.ui.form.MModelProperty, osparc.component.filter.MFilterable],

  construct: function(menu) {
    this.base(arguments);
    this.set({
      width: 210
    });

    // create a date format like "Oct. 19, 2018 11:31 AM"
    this.__dateFormat = new qx.util.format.DateFormat(
      qx.locale.Date.getDateFormat("medium")
    );
    this.__timeFormat = new qx.util.format.DateFormat(
      qx.locale.Date.getTimeFormat("short")
    );

    this._setLayout(new qx.ui.layout.Canvas());

    let mainLayout = this.__mainLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
      alignY: "middle"
    }));
    this._add(mainLayout, {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0
    });

    if (menu !== null) {
      this.setMenu(menu);
    }

    this.addListener("pointerover", this._onPointerOver, this);
    this.addListener("pointerout", this._onPointerOut, this);
  },

  events: {
    /** (Fired by {@link qx.ui.form.List}) */
    "action": "qx.event.type.Event"
  },

  properties: {
    appearance: {
      refine : true,
      init : "pb-listitem"
    },

    /** The menu instance to show when tapping on the button */
    menu: {
      check : "qx.ui.menu.Menu",
      nullable : true,
      apply : "_applyMenu",
      event : "changeMenu"
    },

    uuid: {
      check: "String",
      apply : "_applyUuid"
    },

    studyTitle: {
      check: "String",
      apply : "_applyStudyTitle",
      nullable : true
    },

    creator: {
      check: "String",
      apply : "_applyCreator",
      nullable : true
    },

    lastChangeDate: {
      check : "Date",
      apply : "_applylastChangeDate",
      nullable : true
    },

    tags: {
      check: "Array",
      apply: "_applyTags"
    }
  },

  members: { // eslint-disable-line qx-rules/no-refs-in-members
    __dateFormat: null,
    __timeFormat: null,

    _forwardStates: {
      focused : true,
      hovered : true,
      selected : true,
      dragover : true
    },

    __mainLayout: null,

    // overridden
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "menu-button":
          control = new qx.ui.form.MenuButton().set({
            width: 30,
            height: 30,
            icon: "@FontAwesome5Solid/ellipsis-v/16",
            focusable: false
          });
          this._add(control, {
            top: 0,
            right: 0
          });
          break;
        case "studyTitle":
          control = new qx.ui.basic.Label(this.getStudyTitle()).set({
            margin: [5, 0],
            font: "title-14",
            anonymous: true
          });
          osparc.utils.Utils.setIdToWidget(control, "studyBrowserListItem_title");
          this.__mainLayout.addAt(control, 0);
          break;
        case "creator":
          control = new qx.ui.basic.Label(this.getCreator()).set({
            rich: true,
            allowGrowY: false,
            anonymous: true
          });
          osparc.utils.Utils.setIdToWidget(control, "studyBrowserListItem_creator");
          this.__mainLayout.addAt(control, 1);
          break;
        case "lastChangeDate":
          control = new qx.ui.basic.Label().set({
            rich: true,
            allowGrowY: false,
            anonymous: true
          });
          osparc.utils.Utils.setIdToWidget(control, "studyBrowserListItem_lastChangeDate");
          this.__mainLayout.addAt(control, 2);
          break;
        case "icon":
          control = new qx.ui.basic.Image(this.getIcon()).set({
            anonymous: true,
            scale: true,
            allowStretchX: true,
            allowStretchY: true,
            height: 120
          });
          this.__mainLayout.addAt(control, 3);
          break;
        case "tags":
          control = new qx.ui.container.Composite(new qx.ui.layout.Flow(5, 3));
          this.__mainLayout.addAt(control, 4);
          break;
      }

      return control || this.base(arguments, id);
    },

    _applyMenu: function(value, old) {
      const menuButton = this.getChildControl("menu-button");
      if (value) {
        menuButton.setMenu(value);
      }
      menuButton.setVisibility(value ? "visible" : "excluded");
    },

    // overridden
    _applyUuid: function(value, old) {
      osparc.utils.Utils.setIdToWidget(this, "studyBrowserListItem_"+value);
    },

    _applyIcon: function(value, old) {
      let icon = this.getChildControl("icon");
      icon.set({
        source: value,
        paddingTop: value && value.match(/^@/) ? 30 : 0
      });
    },

    _applyStudyTitle: function(value, old) {
      let label = this.getChildControl("studyTitle");
      label.setValue(value);
    },

    _applyCreator: function(value, old) {
      let label = this.getChildControl("creator");
      label.setValue(value);
    },

    _applylastChangeDate: function(value, old) {
      let label = this.getChildControl("lastChangeDate");
      if (value) {
        let dateStr = null;
        if (value.getDate() === (new Date()).getDate()) {
          dateStr = this.tr("Today");
        } else if (value.getDate() === (new Date()).getDate() - 1) {
          dateStr = this.tr("Yesterday");
        } else {
          dateStr = this.__dateFormat.format(value);
        }
        const timeStr = this.__timeFormat.format(value);
        label.setValue(dateStr + " " + timeStr);
      } else {
        label.resetValue();
      }
    },

    _applyTags: function(tags) {
      if (osparc.data.Permissions.getInstance().canDo("study.tag")) {
        const tagsContainer = this.getChildControl("tags");
        if (tags.length) {
          tagsContainer.show();
          this.getChildControl("creator").exclude();
          this.getChildControl("lastChangeDate").exclude();
        } else {
          tagsContainer.exclude();
          this.getChildControl("creator").show();
          this.getChildControl("lastChangeDate").show();
        }
        tagsContainer.removeAll();
        tags.forEach(tag => tagsContainer.add(new osparc.ui.basic.Tag(tag.name, tag.color, "studyBrowser")));
      }
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
          this.getStudyTitle(),
          this.getCreator()
        ];
        if (checks.filter(label => label.toLowerCase().trim().includes(data.text)).length == 0) {
          return true;
        }
      }
      if (data.tags && data.tags.length) {
        const tagNames = this.getTags().map(tag => tag.name);
        if (data.tags.filter(tag => tagNames.includes(tag)).length == 0) {
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
  },

  destruct : function() {
    this.__dateFormat.dispose();
    this.__dateFormat = null;
    this.__timeFormat.dispose();
    this.__timeFormat = null;
    this.removeListener("pointerover", this._onPointerOver, this);
    this.removeListener("pointerout", this._onPointerOut, this);
  }
});
