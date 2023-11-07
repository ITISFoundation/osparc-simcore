/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Pedro Crespo (pcrespov)

************************************************************************ */

qx.Class.define("osparc.About", {
  extend: osparc.ui.window.Window,
  type: "singleton",

  construct: function() {
    this.base(arguments, this.tr("About ") + this.self().OSPARC_OFFICIAL);
    this.set({
      layout: new qx.ui.layout.VBox(10),
      maxWidth: this.self().MAX_WIDTH,
      contentPadding: this.self().PADDING,
      showMaximize: false,
      showMinimize: false,
      centerOnAppear: true,
      clickAwayClose: true,
      modal: true
    });
    const closeBtn = this.getChildControl("close-button");
    osparc.utils.Utils.setIdToWidget(closeBtn, "aboutWindowCloseBtn");

    this.__buildLayout();
  },

  statics: {
    MAX_WIDTH: 500,
    PADDING: 15,
    OSPARC_OFFICIAL: "o<sup>2</sup>S<sup>2</sup>PARC"
  },

  members: {
    __buildLayout: function() {
      const color = qx.theme.manager.Color.getInstance().resolve("text");

      const poweredByLabel = new qx.ui.basic.Label().set({
        font: "text-14",
        maxWidth: this.self().MAX_WIDTH - 2*this.self().PADDING,
        rich: true,
        wrap: true
      });
      this.add(poweredByLabel);
      const displayName = osparc.store.StaticInfo.getInstance().getDisplayName();
      const poweredText = ` is powered by the <a href='https://github.com/ITISFoundation/osparc-simcore' style='color: ${color}' target='_blank'>${osparc.About.OSPARC_OFFICIAL}</a> platform.`;
      poweredByLabel.setValue(displayName + poweredText);

      const text = this.tr("\
         is an online-accessible, cloud-based, and collaborative computational modeling platform \
        that was developed under the Common Fund’s Stimulating Peripheral Activity to Relieve Conditions \
        (SPARC) program to ensure sustainable, reproducible, and FAIR (findable, accessible, interoperable, reusable) \
        computational modeling in the field of bioelectronic medicine – from neural interfaces to peripheral nerve recruitment \
        and the resulting effects on organ function.<br><br>\
        For more information about SPARC and the services offered, visit the \
      ");
      const portalLink = `<a href='https://sparc.science/' style='color: ${color}' target='_blank'>SPARC Portal</a>.`;
      const aboutText = this.self().OSPARC_OFFICIAL + text + portalLink;
      const aboutLabel = new qx.ui.basic.Label().set({
        value: aboutText,
        font: "text-14",
        maxWidth: this.self().MAX_WIDTH - 2*this.self().PADDING,
        rich: true,
        wrap: true
      });
      this.add(aboutLabel);

      const introText = this.tr("The platform is built upon a number of open-source \
      resources - we can't do it all alone! Some of the technologies that we leverage include:");
      const introLabel = new qx.ui.basic.Label().set({
        value: introText,
        font: "text-14",
        maxWidth: this.self().MAX_WIDTH - 2*this.self().PADDING,
        rich: true,
        wrap: true
      });
      this.add(introLabel);

      const tabView = new qx.ui.tabview.TabView().set({
        contentPaddingTop: 10,
        contentPaddingLeft: 0,
        barPosition: "top"
      });
      tabView.getChildControl("pane").setBackgroundColor("background-main-2");
      this.add(tabView, {
        flex: 1
      });

      const frontendPage = this.__createTabPage(this.tr("Front-end"));
      tabView.add(frontendPage);
      this.__populateFrontendEntries(frontendPage);

      const backendPage = this.__createTabPage(this.tr("Back-end"));
      tabView.add(backendPage);
      this.__populateBackendEntries(backendPage);
    },

    __createTabPage: function(title) {
      const layout = new qx.ui.layout.Grid(5, 5);
      layout.setColumnFlex(0, 1);
      layout.setColumnFlex(1, 1);
      const tabPage = new qx.ui.tabview.Page(title).set({
        layout,
        backgroundColor: "background-main-2"
      });
      return tabPage;
    },

    __populateFrontendEntries: function(page) {
      const entries = [
        this.__createFrontendEntries([osparc.utils.LibVersions.getPlatformVersion()]),
        this.__createFrontendEntries([osparc.utils.LibVersions.getUIVersion()]),
        this.__createFrontendEntries([osparc.utils.LibVersions.getQxCompiler()]),
        this.__createFrontendEntries(osparc.utils.LibVersions.getQxLibraryInfoMap()),
        this.__createFrontendEntries(osparc.utils.LibVersions.get3rdPartyLibs())
      ].flat();
      for (let i=0; i<entries.length; i++) {
        const entry = entries[i];
        if (entry.length) {
          page.add(entry[0], {
            row: i,
            column: 0
          });
        }
        if (entry.length>1) {
          page.add(entry[1], {
            row: i,
            column: 1
          });
        }
      }
    },

    __populateBackendEntries: function(page) {
      const libs = osparc.utils.LibVersions.getBackendLibs();
      for (let i=0; i<libs.length; i++) {
        const entry = this.__createEntry(libs[i]);
        if (entry.length) {
          page.add(entry[0], {
            row: i,
            column: 0
          });
        }
        if (entry.length>1) {
          page.add(entry[1], {
            row: i,
            column: 1
          });
        }
      }
    },

    __createFrontendEntries: function(libs) {
      const entries = [];
      libs.forEach(lib => {
        entries.push(this.__createEntry(lib));
      });
      return entries;
    },

    __createEntry: function(lib) {
      const label = lib.name || "unknown-library";
      const version = lib.version || "-";
      const url = lib.url || null;
      const thumbnail = lib.thumbnail || null;

      if (thumbnail) {
        const image = new qx.ui.basic.Image(thumbnail).set({
          height: 30,
          maxWidth: this.self().MAX_WIDTH - 2*this.self().PADDING,
          scale: true,
          toolTipText: label + (version === "-" ? "" : (" " + version))
        });
        image.getContentElement().setStyles({
          "object-fit": "contain",
          "object-position": "left"
        });
        if (url) {
          image.set({
            cursor: "pointer"
          });
          image.addListener("tap", () => window.open(url));
        }
        return [image];
      }

      let entryLabel;
      if (url) {
        entryLabel = new osparc.ui.basic.LinkLabel(label, url).set({
          font: "link-label-14"
        });
      } else {
        entryLabel = new qx.ui.basic.Label(label);
        entryLabel.set({
          font: "text-14"
        });
      }
      const entryVersion = new qx.ui.basic.Label(version);
      entryVersion.setFont("text-14");
      return [entryLabel, entryVersion];
    }
  }
});
