/* ************************************************************************

   osparc - an entry point to oSparc

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.product.landingPage.s4llite.Content", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(80).set({
      alignX: "center",
      alignY: "middle"
    }));

    this.setPadding(50);

    this.buildLayout();
  },

  statics: {
    createTabPage: function(title, imageSrc, text) {
      const page = new qx.ui.tabview.Page(title);
      page.setLayout(new qx.ui.layout.HBox(10));
      const tabButton = page.getChildControl("button");
      tabButton.set({
        alignX: "right"
      });
      tabButton.getChildControl("label").set({
        font: "text-16",
        textAlign: "right",
        alignX: "right",
        width: 220
      });
      const image = new qx.ui.basic.Image(imageSrc).set({
        width: 600,
        height: 350,
        scale: true
      });
      page.add(image);
      const label = new qx.ui.basic.Label(text).set({
        font: "text-16",
        width: 200,
        rich: true,
        wrap: true,
        alignY: "middle"
      });
      page.add(label);
      return page;
    },

    createVerticalCard: function(imageSrc, title, text) {
      const stepLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(15).set({
        alignX: "center",
        alignY: "middle"
      }));
      const image = new qx.ui.basic.Image(imageSrc).set({
        width: 325,
        height: 230,
        scale: true
      });
      stepLayout.add(image);
      const labelTitle = new qx.ui.basic.Label(title).set({
        font: "text-20",
        textAlign: "center",
        width: 220,
        rich: true,
        wrap: true
      });
      stepLayout.add(labelTitle);
      const labelText = new qx.ui.basic.Label(text).set({
        font: "text-16",
        textAlign: "center",
        width: 220,
        rich: true,
        wrap: true
      });
      stepLayout.add(labelText);
      return stepLayout;
    }
  },

  members: {
    buildLayout: function() {
      const contentTryItOut = this.__createContentTryItOut();
      this._add(contentTryItOut);

      const contentUsers = this.__createContentUsers();
      this._add(contentUsers);

      const contentTabbedLaptop = this.__createContentTabbedLaptop();
      this._add(contentTabbedLaptop);

      const content3Tabs = this.__createContent3Tabs();
      this._add(content3Tabs);

      const contentPartners = this.__createContentPartners();
      this._add(contentPartners);

      const contentPhysics = this.__createContentPhysics();
      this._add(contentPhysics);

      const contentTestimonials = this.__createContentTestimonials();
      this._add(contentTestimonials);

      const contentTemplates = this.__createContentTemplates();
      this._add(contentTemplates);

      const contentCreateAccount = this.__createContentCreateAccount();
      this._add(contentCreateAccount);
    },

    __createContentTryItOut: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(50).set({
        alignX: "center",
        alignY: "middle"
      }));

      const leftLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      })).set({
        width: 450,
        maxWidth: 450
      });

      const text1 = new qx.ui.basic.Label().set({
        value: this.tr("Revolutionary simulation platform, combining computable human phantoms with the most powerful physics solvers and the most advanced tissue models"),
        font: "text-24",
        rich: true,
        wrap: true
      });
      leftLayout.add(text1);

      const text2 = new qx.ui.basic.Label().set({
        value: this.tr("Directly analyzing biological real-world phenomena and complex technical devices in a validated biological and anatomical environment, it also offers leading performance with all the features expected from a multiphysics CAE/TCAD platform."),
        font: "text-16",
        rich: true,
        wrap: true
      });
      leftLayout.add(text2);

      const tryItOutButton = new qx.ui.form.Button().set({
        appearance: "strong-button",
        label: this.tr("Try it out"),
        font: "text-18",
        center: true,
        padding: 20,
        allowGrowX: false,
        width: 180
      });
      tryItOutButton.getContentElement().setStyles({
        "border-radius": "8px"
      });
      leftLayout.add(tryItOutButton);

      contentLayout.add(leftLayout, {
        width: "50%"
      });

      const image = new qx.ui.basic.Image().set({
        source: "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/lite/extra/bunny.png",
        scale: true,
        alignX: "center",
        maxWidth: 400,
        maxHeight: 300
      });
      contentLayout.add(image, {
        width: "50%"
      });

      return contentLayout;
    },

    __createContentUsers: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      }));

      const text1 = new qx.ui.basic.Label().set({
        value: this.tr("Trusted by 100+ users"),
        font: "text-16",
        width: 160,
        rich: true,
        wrap: true
      });
      contentLayout.add(text1);

      const usersLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: "center",
        alignY: "middle"
      }));

      const size = 48;
      [{
        user: "https://github.com/AntoninoMarioC",
        avatar: "https://avatars.githubusercontent.com/u/34208500"
      }, {
        user: "https://github.com/drniiken",
        avatar: "https://avatars.githubusercontent.com/u/32800795"
      }, {
        user: "https://github.com/elisabettai",
        avatar: "https://avatars.githubusercontent.com/u/18575092"
      }, {
        user: "https://github.com/GitHK",
        avatar: "https://avatars.githubusercontent.com/u/5694077"
      }, {
        user: "https://github.com/ignapas",
        avatar: "https://avatars.githubusercontent.com/u/4764217"
      }, {
        user: "https://github.com/mrnicegyu11",
        avatar: "https://avatars.githubusercontent.com/u/8209087"
      }, {
        user: "https://github.com/mguidon",
        avatar: "https://avatars.githubusercontent.com/u/33161876"
      }, {
        user: "https://github.com/matusdrobuliak66",
        avatar: "https://avatars.githubusercontent.com/u/60785969"
      }, {
        user: "https://github.com/odeimaiz",
        avatar: "https://avatars.githubusercontent.com/u/33152403"
      }, {
        user: "https://github.com/pcrespov",
        avatar: "https://avatars.githubusercontent.com/u/32402063"
      }, {
        user: "https://github.com/sanderegg",
        avatar: "https://avatars.githubusercontent.com/u/35365065"
      }, {
        user: "https://github.com/Surfict",
        avatar: "https://avatars.githubusercontent.com/u/4354348"
      }].forEach(user => {
        const link = user.avatar + "?s=" + size;
        const image = new qx.ui.basic.Image().set({
          source: link,
          scale: true,
          maxWidth: size,
          maxHeight: size,
          cursor: "pointer"
        });
        image.addListener("tap", () => window.open(user.user, "_blank"));
        image.getContentElement().setStyles({
          "border-radius": "16px"
        });
        usersLayout.add(image);
      });
      contentLayout.add(usersLayout);

      return contentLayout;
    },

    __createContentTabbedLaptop: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      }));

      const text1 = new qx.ui.basic.Label().set({
        value: this.tr("Access, run and share simulations in the cloud from any browser"),
        font: "text-24",
        textAlign: "center",
        width: 380,
        rich: true,
        wrap: true
      });
      contentLayout.add(text1);

      const tabs = new qx.ui.tabview.TabView().set({
        contentPadding: 20,
        barPosition: "left",
        allowGrowX: false,
        alignX: "center"
      });
      [{
        title: "Cloud-Native",
        image: "https://www.simscale.com/wp-content/uploads/2022/11/e-motor-cooling-simulation-with-webside-laptop-and-computer-1.png",
        text: "No VPN, No remote desktop. True SaaS with instant access anywhere & anytime from a browser without any special hardware."
      }, {
        title: "One Platform, broad Physics",
        image: "https://www.simscale.com/wp-content/uploads/2022/11/multiple-physics-simulations-laptop.gif",
        text: "No disconnected tools used in silos. A single platform with broad physics capabilities for both rough early- and detailed late-stage simulations."
      }, {
        title: "Real-time Collaboration",
        image: "https://www.simscale.com/wp-content/uploads/2022/11/e-motor-cooling-simulation-with-users-laptop.png",
        text: "Google-Docs-style collaboration built-in, enabling unparalleled in-app support as well as sharing simulations with colleagues."
      }, {
        title: "Any Scale",
        image: "https://www.simscale.com/wp-content/uploads/2022/12/e-motor-cooling-simulation-with-simulation-runs-laptop.png",
        text: "Practically no limits to simulation size, number of parallel simulations and storage. From one-off runs to programmatic design space exploration."
      }, {
        title: "Cost-effective",
        image: "https://www.simscale.com/wp-content/uploads/2022/11/pricing-page-laptop-1.png",
        text: "Capex-free, low ‘total cost of ownership’. Economically viable from a single user to 100s of seats. "
      }].forEach(tab => {
        const tabPage = this.self().createTabPage(tab.title, tab.image, tab.text);
        tabs.add(tabPage);
      });
      let i = 0;
      const children = tabs.getChildren();
      setInterval(() => {
        tabs.setSelection([children[i]]);
        i++;
        if (i === children.length) {
          i = 0;
        }
      }, 5000);
      contentLayout.add(tabs);

      return contentLayout;
    },

    __createContent3Tabs: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      }));

      const text1 = new qx.ui.basic.Label().set({
        value: this.tr("HOW IT WORKS"),
        font: "text-18",
        textAlign: "center",
        width: 360,
        rich: true,
        wrap: true
      });
      contentLayout.add(text1);

      const text2 = new qx.ui.basic.Label().set({
        value: this.tr("Well separated contexts, we have three tabs/buttons, my friend"),
        font: "text-24",
        textAlign: "center",
        width: 360,
        rich: true,
        wrap: true
      });
      contentLayout.add(text2);

      const stepsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(30).set({
        alignX: "center",
        alignY: "middle"
      }));
      [{
        image: "https://www.simscale.com/wp-content/uploads/2023/01/step-1-cad-import.png",
        title: "Modeling",
        text: "Upload, import CAD models or build your own model with our amazing tools"
      }, {
        image: "https://www.simscale.com/wp-content/uploads/2023/01/step-2-simulation-setup.png",
        title: "Simulation",
        text: "Define physics and run simulation in the cloud"
      }, {
        image: "https://www.simscale.com/wp-content/uploads/2023/01/step-3-design-decision.png",
        title: "Post Processing",
        text: "We also have a PP Calc"
      }].forEach(tab => {
        const verticalCard = this.self().createVerticalCard(tab.image, tab.title, tab.text);
        stepsLayout.add(verticalCard);
      });
      contentLayout.add(stepsLayout);

      return contentLayout;
    },

    __createContentPartners: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      }));

      const text1 = new qx.ui.basic.Label().set({
        value: this.tr("Our partners"),
        font: "text-16",
        width: 160,
        rich: true,
        wrap: true
      });
      contentLayout.add(text1);

      const partnersLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(50).set({
        alignX: "center",
        alignY: "middle"
      }));

      [{
        link: "https://speag.swiss/",
        avatar: "https://speag.swiss/resources/themes/speag/images/logo.png"
      }, {
        link: "https://itis.swiss/",
        avatar: "https://itis.swiss/resources/themes/itis/images/logo.png"
      }, {
        link: "https://zmt.swiss/",
        avatar: "https://d2jx2rerrg6sh3.cloudfront.net/image-handler/picture/2019/10/logo-ZMT-3.png"
      }].forEach(partner => {
        const image = new qx.ui.basic.Image().set({
          source: partner.avatar,
          scale: true,
          maxWidth: 200,
          maxHeight: 50,
          cursor: "pointer"
        });
        image.addListener("tap", () => window.open(partner.link, "_blank"));
        partnersLayout.add(image);
      });
      contentLayout.add(partnersLayout);

      return contentLayout;
    },

    __createContentPhysics: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      }));

      const text1 = new qx.ui.basic.Label().set({
        value: this.tr("AVAILABLE PHYSICS"),
        font: "text-18",
        textAlign: "center",
        width: 360,
        rich: true,
        wrap: true
      });
      contentLayout.add(text1);

      const text2 = new qx.ui.basic.Label().set({
        value: this.tr("A broad range of physics based on best-of-breed simulation solvers"),
        font: "text-24",
        textAlign: "center",
        width: 450,
        rich: true,
        wrap: true
      });
      contentLayout.add(text2);

      const grid = new qx.ui.layout.Grid(20, 10);
      const gridLayout = new qx.ui.container.Composite(grid).set({
        allowGrowX: false
      });
      [{
        image: "https://zmt.swiss/assets/images/sim4life/physics_models/EM01b.jpg",
        title: "EM Full Wave",
        text: "The Electromagnetics Full Wave Solvers (P-EM-FDTD) enable accelerated full-wave, large-scale EM modeling (> billion voxels) with Yee discretization on geometrically adaptive, inhomogeneous, rectilinear meshes with conformal sub-cell correction and thin layer models, with support for dispersive materials."
      }, {
        image: "https://zmt.swiss/assets/images/sim4life/physics_models/EM02b.jpg",
        title: "Quasi-Static EM",
        text: "The Quasi-Static Electromagnetic Solvers (P-EM-QS) enable the efficient modeling of static and quasi-static EM regimes by applying the finite element method on graded voxel meshes."
      }, {
        image: "https://zmt.swiss/assets/images/sim4life/physics_models/thermo01b.jpg",
        title: "Thermodynamics",
        text: "The Thermodynamic Solvers (P-THERMAL) enable the modeling of heat transfer in living tissue using advanced perfusion and thermoregulation models."
      }, {
        image: "https://zmt.swiss/assets/images/sim4life/tissue_models/vagusnerve.png",
        title: "Neuronal Models",
        text: "The Neuronal Tissue Models (T-NEURO) enable the dynamic modeling of EM-induced neuronal activation, inhibition, and synchronization using either complex, multi-compartmental representations of axons, neurons, and neuronal networks with varying channel dynamics, or generic models."
      }, {
        image: "https://zmt.swiss/assets/images/sim4life/physics_models/acoustics01B.jpg",
        title: "Acoustics",
        text: "Sim4Life offers a novel full-wave Acoustics Solver (P-ACOUSTICS) based on the linear pressure wave equation (LAPWE), extended and optimized for heterogeneous, lossy materials for the modeling of the propagation of pressure waves through highly inhomogeneous media like tissue and bone."
      }].forEach((physics, idx) => {
        grid.setColumnAlign(idx, "center", "top");
        grid.setRowAlign(0, "center", "middle"); // image

        const verticalCard = this.self().createVerticalCard(physics.image, physics.title, physics.text);
        const text = verticalCard.getChildren()[2];
        text.set({
          height: 230
        });
        gridLayout.add(text, {
          row: 2,
          column: idx
        });
        gridLayout.add(verticalCard.getChildren()[1], {
          row: 1,
          column: idx
        });
        const image = verticalCard.getChildren()[0];
        image.set({
          width: 240,
          height: 180
        });
        image.getContentElement().setStyles({
          "border-radius": "8px"
        });
        gridLayout.add(image, {
          row: 0,
          column: idx
        });
      });
      contentLayout.add(gridLayout);

      return contentLayout;
    },

    __createContentTestimonials: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      }));

      const grid = new qx.ui.layout.Grid(10, 10);
      grid.setColumnAlign(0, "center", "bottom");
      const testimonyGrid = new qx.ui.container.Composite(grid).set({
        allowGrowX: false
      });
      const testimonyImage = new qx.ui.basic.Image().set({
        scale: true,
        maxWidth: 200,
        maxHeight: 50
      });
      testimonyGrid.add(testimonyImage, {
        row: 0,
        column: 0
      });
      const testimonyLabel = new qx.ui.basic.Label().set({
        font: "text-18",
        width: 300,
        rich: true,
        wrap: true,
        textAlign: "center"
      });
      testimonyGrid.add(testimonyLabel, {
        row: 1,
        column: 0
      });
      const testimoneerName = new qx.ui.basic.Label().set({
        font: "text-16",
        width: 300,
        rich: true,
        wrap: true,
        textAlign: "center"
      });
      testimonyGrid.add(testimoneerName, {
        row: 2,
        column: 0
      });
      const testimoneerPosition = new qx.ui.basic.Label().set({
        font: "text-14",
        width: 300,
        rich: true,
        wrap: true,
        textAlign: "center"
      });
      testimonyGrid.add(testimoneerPosition, {
        row: 3,
        column: 0
      });
      contentLayout.add(testimonyGrid);

      const usersLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: "center",
        alignY: "middle"
      }));

      const imageSelected = image => {
        image.getContentElement().setStyles({
          "border-width": "2px",
          "border-radius": "16px",
          "border-style": "double",
          "border-color": qx.theme.manager.Color.getInstance().resolve("strong-main")
        });
      };
      const imageUnselected = image => {
        image.getContentElement().setStyles({
          "border-width": "0px",
          "border-radius": "16px"
        });
      };
      const images = [];
      const size = 48;
      [{
        user: "https://media.licdn.com/dms/image/C5603AQHs0nDSqMOHUg/profile-displayphoto-shrink_800_800/0/1583841526403?e=2147483647&v=beta&t=cCyNaotxPTOCWDG9DZm3YJntF92OTgqlCL5T9kZzBfs",
        testimoneerCompany: "https://itis.swiss/resources/themes/itis/images/logo.png",
        testimony: "Thank you guys for your help these past 2 weeks! What an adventure :). Looking forward to the next one!",
        testimoneerName: "Taylor Newton",
        testimoneerPosition: "Descendant of Brook and Isaac"
      }, {
        user: "https://media.licdn.com/dms/image/C4E03AQEPdUlmt0gOZg/profile-displayphoto-shrink_800_800/0/1516647993074?e=2147483647&v=beta&t=Ri3GONAT3ViT2TyzOVvMBRRpEQOiUusnalPMGl4tES8",
        testimoneerCompany: "https://mms.businesswire.com/media/20221108005198/en/1628061/5/9001608_00_logo-ndd.jpg",
        testimony: "Uh oh, I think the study you seek has been deleted from AWS production!",
        testimoneerName: "Katie Zhuang",
        testimoneerPosition: "Technical Product Manager"
      }].forEach((user, idx) => {
        const image = new qx.ui.basic.Image().set({
          source: user.user,
          scale: true,
          maxWidth: size,
          maxHeight: size,
          cursor: "pointer"
        });
        images.push(image);
        image.addListener("tap", () => {
          testimonyImage.setSource(user.testimoneerCompany);
          testimonyLabel.setValue(user.testimony);
          testimoneerName.setValue(user.testimoneerName);
          testimoneerPosition.setValue(user.testimoneerPosition);
        });
        image.getContentElement().setStyles({
          "border-radius": "16px"
        });
        if (idx === 0) {
          testimonyImage.setSource(user.testimoneerCompany);
          testimonyLabel.setValue(user.testimony);
          testimoneerName.setValue(user.testimoneerName);
          testimoneerPosition.setValue(user.testimoneerPosition);
          imageSelected(image);
        }
        usersLayout.add(image);
      });
      images.forEach(image => {
        image.addListener("tap", () => {
          images.forEach(img => imageUnselected(img));
          imageSelected(image);
        });
      });
      contentLayout.add(usersLayout);

      return contentLayout;
    },

    __createContentTemplates: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(30).set({
        alignX: "center",
        alignY: "middle"
      }));

      const createTemplateCard = (image, title, link) => {
        const grid = new qx.ui.layout.Grid(10, 10);
        grid.setColumnAlign(0, "center", "bottom");
        const templateCard = new qx.ui.container.Composite(grid).set({
          allowGrowX: false
        });
        const testimonyImage = new qx.ui.basic.Image(image).set({
          scale: true,
          maxWidth: 190,
          maxHeight: 150
        });
        templateCard.add(testimonyImage, {
          row: 0,
          column: 0
        });
        const testimonyLabel = new qx.ui.basic.Label(title).set({
          font: "text-18",
          width: 190,
          rich: true,
          wrap: true,
          textAlign: "center"
        });
        templateCard.add(testimonyLabel, {
          row: 1,
          column: 0
        });
        const tryItOutButton = new qx.ui.form.Button().set({
          appearance: "strong-button",
          label: this.tr("Try it out"),
          font: "text-18",
          center: true,
          padding: 10,
          allowGrowX: false,
          width: 150
        });
        tryItOutButton.getContentElement().setStyles({
          "border-radius": "8px"
        });
        tryItOutButton.addListener("tap", () => window.open(link, "_blank"));
        templateCard.add(tryItOutButton, {
          row: 2,
          column: 0
        });
        return templateCard;
      };
      [{
        image: "https://github.com/KZzizzle/osparc_images/blob/master/catmap.JPG?raw=true",
        title: "CNN Trainer",
        link: "https://osparc.io/study/b31f2b80-996e-11eb-9a48-02420a0b0129"
      }, {
        image: "https://github.com/KZzizzle/osparc_images/blob/master/SPARC_Report%20(1).png?raw=true",
        title: "SPARC Sample Report",
        link: "https://osparc.io/study/733ddc42-c7a3-11eb-8a4e-02420a0b01de"
      }, {
        image: "https://drive.google.com/uc?id=1w8zGcZlpODX8vYu0_eIJ_HQnds-T8MI9",
        title: "SPARC Metadata Editor",
        link: "https://osparc.io/study/6e0dfe20-1bab-11ed-b162-02420a0b0093"
      }, {
        image: "https://assets.discover.pennsieve.io/dataset-assets/84/1/banner.jpg",
        title: "Neurofauna Rat",
        link: "https://osparc.io/study/13b9ed12-e7aa-11ea-9b21-02420a0b001d"
      }].forEach(template => contentLayout.add(createTemplateCard(template.image, template.title, template.link)));
      return contentLayout;
    },

    __createContentCreateAccount: function() {
      const createAccountLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(15).set({
        alignX: "center",
        alignY: "middle"
      }));

      let message = qx.locale.Manager.tr("Registration is currently only available with an invitation.");
      message += "<br>";
      Promise.all([
        osparc.store.VendorInfo.getInstance().getVendor(),
        osparc.store.StaticInfo.getInstance().getDisplayName()
      ])
        .then(values => {
          const createAccountLabel = new qx.ui.basic.Label().set({
            font: "text-18",
            width: 450,
            rich: true,
            wrap: true,
            textAlign: "center"
          });
          createAccountLayout.add(createAccountLabel);
          const requestAccountButton = new qx.ui.form.Button().set({
            appearance: "strong-button",
            label: this.tr("Request account"),
            font: "text-18",
            center: true,
            padding: 20,
            allowGrowX: false,
            width: 180
          });
          requestAccountButton.getContentElement().setStyles({
            "border-radius": "8px"
          });
          createAccountLayout.add(requestAccountButton);
          const vendor = values[0];
          const displayName = values[1];
          if ("invitation_url" in vendor) {
            message += qx.locale.Manager.tr("Please request access to ") + displayName + ":";
            message += "<br>";
            createAccountLabel.setValue(message);
            requestAccountButton.addListener("tap", () => window.open(vendor["invitation_url"], "_blank"));
          } else {
            message += qx.locale.Manager.tr("Please contact:");
            createAccountLabel.setValue(message);
            osparc.store.VendorInfo.getInstance().getSupportEmail()
              .then(supportEmail => {
                const mailto = this.getMailToLabel(supportEmail, "Request Account " + displayName);
                requestAccountButton.addListener("tap", () => window.open(mailto, "_blank"));
              });
          }
        });
      return createAccountLayout;
    }
  }
});
