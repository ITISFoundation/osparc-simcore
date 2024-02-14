/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.editor.ThumbnailSuggestions", {
  extend: osparc.widget.SlideBar,

  construct: function(study) {
    this.base(arguments);

    this.set({
      alignX: "center",
      maxHeight: 170
    });
    this.setButtonsWidth(30);

    this.__thumbnails = [];

    if (study) {
      this.setStudy(study);
    }
  },

  events: {
    "thumbnailAdded": "qx.event.type.Event",
    "thumbnailTapped": "qx.event.type.Data"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      nullable: false,
      init: null,
      apply: "__applyStudyData"
    }
  },

  statics: {
    defaultTemplates: [
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/Thumbnail.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/bright_coulomb.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/dynamic_hertz.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/electric_heaviside.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/energetic_ampere.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/glowing_tesla.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/illuminated_volta.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/luminous_ohm.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/magnetic_lorentz.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/radiant_maxwell.png",
      "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/project_thumbnails/vibrant_faraday.png"
    ],
    extractThumbnailSuggestions: function(study) {
      const suggestions = new Set([]);
      const wb = study.getWorkbench();
      const nodes = wb.getWorkbenchInitData() ? wb.getWorkbenchInitData() : wb.getNodes();
      Object.values(nodes).forEach(node => {
        const srvMetadata = osparc.service.Utils.getMetaData(node.getKey(), node.getVersion());
        if (srvMetadata && srvMetadata["thumbnail"] && !osparc.data.model.Node.isFrontend(node)) {
          suggestions.add(srvMetadata["thumbnail"]);
        }
      });
      const amendedArray = [...suggestions, ...this.defaultTemplates]
      return Array.from(amendedArray);
    }
  },

  members: {
    __thumbnails: null,

    __addThumbnail: function(thumbnailData) {
      this.__thumbnails.push(thumbnailData);
      this.fireEvent("thumbnailAdded");
    },

    __applyStudyData: function(study) {
      const wb = study.getWorkbench();
      const nodes = wb.getWorkbenchInitData() ? wb.getWorkbenchInitData() : wb.getNodes();
      Object.values(nodes).forEach(node => {
        const srvMetadata = osparc.service.Utils.getMetaData(node.getKey(), node.getVersion());
        if (srvMetadata && srvMetadata["thumbnail"] && !osparc.data.model.Node.isFrontend(node)) {
          this.__addThumbnail({
            type: "serviceImage",
            thumbnailUrl: srvMetadata["thumbnail"],
            fileUrl: srvMetadata["thumbnail"]
          });
        }
      });
      this.__reloadSuggestions();
    },

    addWorkbenchUIPreviewToSuggestions: function() {
      this.__addThumbnail({
        type: "workbenchUIPreview",
        thumbnailUrl: osparc.product.Utils.getWorkbenchUIPreviewPath(),
        fileUrl: osparc.product.Utils.getWorkbenchUIPreviewPath()
      });
      this.__reloadSuggestions();

      const themeManager = qx.theme.manager.Meta.getInstance();
      themeManager.addListener("changeTheme", () => this.addWorkbenchUIPreviewToSuggestions());
    },

    addPreviewsToSuggestions: function(previewsPerNodes) {
      previewsPerNodes.forEach(previewsPerNode => {
        const previews = previewsPerNode["screenshots"];
        if (previews && previews.length) {
          previews.forEach(preview => {
            if (preview["mimetype"]) {
              this.__addThumbnail({
                type: preview["mimetype"],
                thumbnailUrl: preview["thumbnail_url"],
                fileUrl: preview["file_url"]
              });
            }
          });
          this.__reloadSuggestions();
        }
      });
    },

    __reloadSuggestions: function() {
      this.setSuggestions(this.__thumbnails);
    },

    thumbnailTapped: function(thumbnail) {
      this.getChildren().forEach(thumbnailImg => {
        osparc.utils.Utils.updateBorderColor(thumbnailImg, qx.theme.manager.Color.getInstance().resolve("box-shadow"));
        osparc.utils.Utils.addBackground(thumbnailImg, qx.theme.manager.Color.getInstance().resolve("fab-background"));
      });
      const color = qx.theme.manager.Color.getInstance().resolve("background-selected-dark");
      const bgColor = qx.theme.manager.Color.getInstance().resolve("background-selected");
      osparc.utils.Utils.updateBorderColor(thumbnail, color);
      osparc.utils.Utils.addBackground(thumbnail, bgColor);
      this.fireDataEvent("thumbnailTapped", {
        type: thumbnail.thumbnailType || "templateThumbnail",
        source: thumbnail.thumbnailFileUrl || thumbnail.getSource()
      });
    },

    setSuggestions: function(suggestions) {
      this.removeAll();
      suggestions.forEach(suggestion => {
        const maxHeight = this.getMaxHeight();
        const thumbnail = new osparc.ui.basic.Thumbnail(suggestion["thumbnailUrl"] || suggestion, maxHeight, parseInt(maxHeight*2/3));
        thumbnail.set({
          minWidth: 97,
          margin: 0,
          decorator: "thumbnail"
        });
        thumbnail.thumbnailType = suggestion["type"] || "templateThumbnail";
        thumbnail.thumbnailFileUrl = suggestion["fileUrl"] || suggestion;
        thumbnail.addListener("mouseover", () => thumbnail.set({decorator: "thumbnail-selected"}), this);
        thumbnail.addListener("mouseout", () => thumbnail.set({decorator: "thumbnail"}), this);
        thumbnail.addListener("tap", () => {
          this.thumbnailTapped(thumbnail);
        }, this);
        this.add(thumbnail);
      });
    }
  }
});
