/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * Display widget with a title bar and collapsible content.
 */
qx.Class.define("qxapp.desktop.PanelView", {
  extend: qx.ui.core.Widget,

  construct: function(title, content) {
    this.base(arguments);

    // Internal props
    this.__titleBar = null;
    this.__titleLabel = null;
    this.__caret = null;

    // Layout
    const layout = new qx.ui.layout.VBox();
    this._setLayout(layout);

    // Title bar
    this.__titleBar = new qx.ui.container.Composite(new qx.ui.layout.HBox(5))
      .set({
        appearance: "titlebar"
      });
    this._add(this.__titleBar);

    if (title){
      this.setTitle(title);
    }

    // Content
    if (content) {
      content.setAppearance("panelview-content");
      this.setContent(content);
    }

    // Attach handlers
    this.__attachEventHandlers();
  },

  properties: {

    title: {
      check: "String",
      nullable: true,
      apply: "_applyTitle"
    },

    content: {
      check: "qx.ui.core.Widget",
      nullable: true,
      apply: "_applyContent"
    },

    contentVisibility: {
      init: true,
      check: "Boolean",
      apply: "_applyContentVisibility"
    }
  },

  members: {

    toggleContentVisibility: function() {
      this.setContentVisibility(!this.getContentVisibility());
    },

    _applyContentVisibility: function(isVisible) {
      if (this.getContent()) {
        this.__caret.setSource(this.getContentVisibility() ? lessCaret : moreCaret);
        if (isVisible) {
          // BUGGY. Not using setTimeout causes weird rendering issue in QX. Using it causes a small flicker.
          this.getContent().setVisibility("visible");
          setTimeout(() => qx.bom.element.Animation.animateReverse(this.getContent().getContentElement().getDomElement(),
            contentTransition(this.getContent().getContentElement().getDomElement().style.height)), 0);
        } else {
          qx.bom.element.Animation.animate(this.getContent().getContentElement().getDomElement(),
            contentTransition(this.getContent().getContentElement().getDomElement().style.height));
          setTimeout(() => this.getContent().setVisibility("excluded"), contentTransition().duration - 10);
        }
      }
    },

    _applyContent: function(content, oldContent) {
      const contentIndex = this._indexOf(oldContent);
      if (contentIndex > -1) {
        this._removeAt(contentIndex);
      }
      content.set({
        appearance: "panelview-content",
        decorator: "panelview-content"
      });
      this._addAt(content, 1, { flex: 1 });

      if (this.__caret == null) {
        this.__caret = new qx.ui.basic.Image(this.getContentVisibility() ? lessCaret : moreCaret).set({
          marginTop: 2
        });
        this.__titleBar.add(this.__caret);
      }
    },

    _applyTitle: function(title) {
      if (this.__titlelabel) {
        this.__titleLabel.setValue(title);
      } else {
        this.__titleLabel = new qx.ui.basic.Label(title)
          .set({
            appearance: "titlebar-label",
            font: "title-14"
          });
        this.__titleBar.add(this.__titleLabel);
      }
    },

    __attachEventHandlers() {
      this.__titleBar.addListener("tap", () => {
        this.toggleContentVisibility();
      }, this);
    }
  }

});

const contentTransition = height => ({
  duration: 200,
  timing: "ease-in",
  keyFrames: {
    0: { height: height },
    100: { height: 0 }
  }
});

const moreCaret = "@MaterialIcons/expand_more/20";
const lessCaret = "@MaterialIcons/expand_less/20";
