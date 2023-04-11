#/***************************************************************************
# GpuDataChecker
#
# Data Checker for "geoportail-urbanisme" integration
#							 -------------------
#		begin				: 2022-10-28
#		git sha				: $Format:%H$
#		copyright			: (C) 2022 by IGN
#		email				: paul-emmanuel.gautreau@ign.fr
# ***************************************************************************/
#
#/***************************************************************************
# *																		 *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU General Public License as published by  *
# *   the Free Software Foundation; either version 2 of the License, or	 *
# *   (at your option) any later version.								   *
# *																		 *
# ***************************************************************************/

#################################################
# Edit the following to match your sources lists
#################################################
VERSION=0.1.0
PLUGINNAME = gpu-data-checker

PY_FILES = \
	gpuDataChecker.py \
	__init__.py

EXTRAS = metadata.txt

COMPILED_RESOURCE_FILES = resources.py


#################################################
# Normally you would not need to edit below here
#################################################

QGISDIR=$(HOME)/.local/share/QGIS/QGIS3/profiles/default

default: compile

compile:
	pyrcc5 -o resources.py resources.qrc

test: deploy
	@echo
	@echo "----------------------"
	@echo "Regression Test Suite"
	@echo "----------------------"
	qgis --defaultui --code test/src/testMappingTools.py

deploy: compile
	@echo
	@echo "------------------------------------------"
	@echo "Deploying plugin to your .qgis3 directory."
	@echo "------------------------------------------"
	# The deploy  target only works on unix like operating system where
	# the Python plugin directory is located at:  $(QGISDIR)/python/plugins
	mkdir -p $(QGISDIR)/python/plugins/$(PLUGINNAME)
	cp -vf $(PY_FILES) $(QGISDIR)/python/plugins/$(PLUGINNAME)
	cp -vf $(COMPILED_RESOURCE_FILES) $(QGISDIR)/python/plugins/$(PLUGINNAME)
	cp -vf $(EXTRAS) $(QGISDIR)/python/plugins/$(PLUGINNAME)

# The dclean target removes compiled python files from plugin directory
# also deletes any .git entry
dclean:
	@echo
	@echo "-----------------------------------"
	@echo "Removing any compiled python files."
	@echo "-----------------------------------"
	find $(QGISDIR)/python/plugins/$(PLUGINNAME) -iname "*.pyc" -delete
	find $(QGISDIR)/python/plugins/$(PLUGINNAME) -iname ".git" -prune -exec rm -Rf {} \;
	rm -rf __pycache__


derase:
	@echo
	@echo "-------------------------"
	@echo "Removing deployed plugin."
	@echo "-------------------------"
	rm -Rf $(QGISDIR)/python/plugins/$(PLUGINNAME)

zip: deploy dclean
	@echo
	@echo "---------------------------"
	@echo "Creating plugin zip bundle."
	@echo "---------------------------"
	# The zip target deploys the plugin and creates a zip file with the deployed
	# content. You can then upload the zip file on http://plugins.qgis.org
	rm -f $(PLUGINNAME).zip
	cd $(QGISDIR)/python/plugins; zip -9r $(CURDIR)/$(PLUGINNAME).zip $(PLUGINNAME)

package: compile
	# Create a zip package of the plugin named $(PLUGINNAME).zip.
	# This requires use of git (your plugin development directory must be a
	# git repository).
	# To use, pass a valid commit or tag as follows:
	#   make package VERSION=Version_0.3.2
	@echo
	@echo "------------------------------------"
	@echo "Exporting plugin to zip package.	"
	@echo "------------------------------------"
	rm -f $(PLUGINNAME).zip
	git archive --prefix=$(PLUGINNAME)/ -o $(PLUGINNAME).zip $(VERSION)
	echo "Created package: $(PLUGINNAME).zip"

upload: zip
	@echo
	@echo "-------------------------------------"
	@echo "Uploading plugin to QGIS Plugin repo."
	@echo "-------------------------------------"
	$(PLUGIN_UPLOAD) $(PLUGINNAME).zip

clean:
	@echo
	@echo "------------------------------------"
	@echo "Removing uic and rcc generated files"
	@echo "------------------------------------"
	rm $(COMPILED_RESOURCE_FILES)