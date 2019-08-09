/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * @asset(gridsterjs/*)
 */

/* global $ */

/**
 * A qooxdoo wrapper for
 * <a href='https://github.com/dsmorse/gridster.js' target='_blank'>gridsterjs</a>
 */

qx.Class.define("osparc.wrapper.Gridster", {
  extend: qx.ui.core.Widget,

  statics: {
    NAME: "gridster",
    VERSION: "0.7.0",
    URL: "https://github.com/dsmorse/gridster.js",

    buildHeader: function(cellOutput) {
      let html = "<header>";
      html += cellOutput.getTitle();
      html += "</header>";
      return html;
    },

    buildContent: function(cellOutput) {
      let html = "<content>";
      html += cellOutput.getOutput();
      html += "</content>";
      return html;
    },

    buildHtmlCode: function(cellOutput) {
      let html = this.buildHeader(cellOutput);
      html += this.buildContent(cellOutput);
      return html;
    },

    buildHtmlCodeInList: function(cellOutput) {
      let html = "<li>";
      html += this.buildHtmlCode(cellOutput);
      html += "</li>";
      return html;
    }
  },

  construct: function() {
    this.base(arguments);

    this.addListenerOnce("appear", () => {
      this.__init();
    }, this);
  },

  properties: {
    libReady: {
      nullable: false,
      init: false,
      check: "Boolean"
    },

    atomWidth: {
      nullable: false,
      init: 25,
      check: "Number"
    },

    atomHeight: {
      nullable: false,
      init: 25,
      check: "Number"
    }
  },

  events: {
    "gridsterLibReady": "qx.event.type.Data",
    "widgetSelected": "qx.event.type.Data"
  },

  members: {
    __gridster: null,

    __init: function() {
      // initialize the script loading
      const jQueryPath = "osparc/gridsterjs/jquery-3.3.1.min.js";
      const extras = false;
      const gridsterPath = extras ? "osparc/gridsterjs/jquery.gridster.with-extras-0.7.0.min.js" : "osparc/gridsterjs/jquery.gridster-0.7.0.min.js";
      const gridsterCss = "osparc/gridsterjs/jquery.gridster-0.7.0.min.css";
      const gridsterDemoCss = "osparc/gridsterjs/jquery.gridster.demo.css";
      const gridsterOsparcCss = "osparc/gridsterjs/jquery.gridster.osparc.css";
      const gridsterCssUri = qx.util.ResourceManager.getInstance().toUri(gridsterCss);
      const gridsterDemoCssUri = qx.util.ResourceManager.getInstance().toUri(gridsterDemoCss);
      const gridsterOsparcCssUri = qx.util.ResourceManager.getInstance().toUri(gridsterOsparcCss);
      qx.module.Css.includeStylesheet(gridsterCssUri);
      qx.module.Css.includeStylesheet(gridsterDemoCssUri);
      qx.module.Css.includeStylesheet(gridsterOsparcCssUri);
      let dynLoader = new qx.util.DynamicScriptLoader([
        jQueryPath,
        gridsterPath
      ]);

      dynLoader.addListenerOnce("ready", e => {
        console.log(gridsterPath + " loaded");
        this.setLibReady(true);
        this.__createEmptyLayout();
        this.fireDataEvent("gridsterLibReady", true);
      }, this);

      dynLoader.addListener("failed", e => {
        let data = e.getData();
        console.error("failed to load " + data.script);
        this.fireDataEvent("gridsterLibReady", false);
      }, this);

      dynLoader.start();
    },

    __createEmptyLayout: function() {
      let gridsterPlaceholder = qx.dom.Element.create("div");
      qx.bom.element.Attribute.set(gridsterPlaceholder, "id", "gridster");
      qx.bom.element.Attribute.set(gridsterPlaceholder, "class", "gridster");
      qx.bom.element.Style.set(gridsterPlaceholder, "width", "100%");
      qx.bom.element.Style.set(gridsterPlaceholder, "height", "100%");
      const domEl = this.getContentElement().getDomElement();
      while (domEl.hasChildNodes()) {
        domEl.removeChild(domEl.lastChild);
      }
      domEl.appendChild(gridsterPlaceholder);

      let cellsList = qx.dom.Element.create("ul");
      gridsterPlaceholder.appendChild(cellsList);

      const maxSize = this.__getMaxSize();
      const nColsMax = maxSize.nColsMax;
      const nRowsMax = maxSize.nRowsMax;
      this.__gridster = $(".gridster ul").gridster({
        "widget_base_dimensions": [this.getAtomWidth(), this.getAtomHeight()],
        "widget_margins": [5, 5],
        "max_cols": nColsMax,
        "max_rows": nRowsMax,
        // "helper": "clone",
        "resize": {
          "enabled": true,
          "max_size": [nColsMax, nRowsMax]
        },
        "draggable": {
          "handle": "header"
        }
      })
        .data("gridster");
    },

    __getMaxSize: function() {
      return {
        nColsMax: Math.floor(this.getBounds().width/this.getAtomWidth()),
        nRowsMax: Math.floor(2*this.getBounds().height/this.getAtomHeight())
      };
    },

    addWidget: function(cellOutput) {
      const html = this.self().buildHtmlCodeInList(cellOutput);
      let jQueryElement = this.__gridster.add_widget(html, 400/this.getAtomWidth(), 300/this.getAtomHeight());
      if (jQueryElement) {
        let htmlElement = jQueryElement.get(0);
        htmlElement.addEventListener("dblclick", e => {
          this.fireDataEvent("widgetSelected", cellOutput.getHandler().getUuid());
        }, this);
        return htmlElement;
      }
      return null;
    },

    rebuildWidget: function(cellOutput, htmlElement) {
      let html = this.self().buildHtmlCode(cellOutput);
      html += "<span class='gs-resize-handle gs-resize-handle-both'></span>";
      htmlElement.innerHTML = html;
    }
  }
});
