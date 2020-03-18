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

qx.Class.define("osparc.dashboard.StudyBrowserListBase", {
  extend: qx.ui.form.ToggleButton,
  implement : [qx.ui.form.IModel, osparc.component.filter.IFilterable],
  include : [qx.ui.form.MModelProperty, osparc.component.filter.MFilterable],
  type: "abstract",

  construct: function() {
    this.base(arguments);
    this.set({
      width: this.self().ITEM_WIDTH,
      height: this.self().ITEM_HEIGHT,
      allowGrowX: false
    });

    this._setLayout(new qx.ui.layout.Canvas());

    let mainLayout = this._mainLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
      alignY: "middle"
    }));
    this._add(mainLayout, {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0
    });

    this.addListener("pointerover", this._onPointerOver, this);
    this.addListener("pointerout", this._onPointerOut, this);
  },

  statics: {
    ITEM_WIDTH: 200,
    ITEM_HEIGHT: 200
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

    studyTitle: {
      check: "String",
      apply : "_applyStudyTitle",
      nullable : true
    }
  },

  members: { // eslint-disable-line qx-rules/no-refs-in-members
    _forwardStates: {
      focused : true,
      hovered : true,
      selected : true,
      dragover : true
    },

    _mainLayout: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "studyTitle":
          control = new qx.ui.basic.Label(this.getStudyTitle()).set({
            margin: [5, 0],
            font: "title-14",
            rich : true,
            anonymous: true
          });
          osparc.utils.Utils.setIdToWidget(control, "studyBrowserListNew_title");
          this._mainLayout.addAt(control, 0);
          break;
      }
      return control || this.base(arguments, id);
    },

    _applyStudyTitle: function(value, old) {
      let label = this.getChildControl("studyTitle");
      label.setValue(value);
    },

    _applyIcon: function(value, old) {
      let icon = this.getChildControl("icon");
      icon.set({
        source: value,
        paddingTop: value && value.match(/^@/) ? 30 : 0
      });
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
      throw new Error("Abstract method called!");
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
    this.removeListener("pointerover", this._onPointerOver, this);
    this.removeListener("pointerout", this._onPointerOut, this);
  }
});
