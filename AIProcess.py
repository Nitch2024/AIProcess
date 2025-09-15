#!/usr/bin/env python3
#coding: utf-8

import sys
import os
import tempfile
import subprocess
import time
from functools import partial

import gi
gi.require_version('Gimp', '3.0')
gi.require_version('GimpUi', '3.0')

from gi.repository import Gimp, GimpUi, GObject, GLib, Gio, Gtk

info = {'python-fu-AIScale-RealSR': {'MenuLabel': 'RealSR', 'dir': "realsr-ncnn-vulkan-20220728-windows", 'exe': "realsr-ncnn-vulkan.exe"},
        'python-fu-AIScale-Waifu2x': {'MenuLabel': 'Waifu2x', 'dir': "waifu2x-ncnn-vulkan-20250504-windows", 'exe': "waifu2x-ncnn-vulkan.exe"},
        'python-fu-AIScale-RealCUGAN': {'MenuLabel': 'RealCUGAN', 'dir': "realcugan-ncnn-vulkan-20220728-windows", 'exe': "realcugan-ncnn-vulkan.exe"},
        'python-fu-AIScale-RealESRGAN': {'MenuLabel': 'RealESRGAN', 'dir': "realesrgan-ncnn-vulkan-v0.2.0-windows", 'exe': "realesrgan-ncnn-vulkan.exe"},
        'python-fu-AIScale-SRMD': {'MenuLabel': 'SRMD', 'dir': "srmd-ncnn-vulkan-20220728-windows", 'exe': "srmd-ncnn-vulkan.exe" },
        'python-fu-AIDenoise-RealSR': {'MenuLabel': 'RealSR', 'dir': "realsr-ncnn-vulkan-20220728-windows", 'exe': "realsr-ncnn-vulkan.exe"},
        'python-fu-AIDenoise-Waifu2x': {'MenuLabel': 'Waifu2x', 'dir': "waifu2x-ncnn-vulkan-20250504-windows", 'exe': "waifu2x-ncnn-vulkan.exe"},
        'python-fu-AIDenoise-RealCUGAN': {'MenuLabel': 'RealCUGAN', 'dir': "realcugan-ncnn-vulkan-20220728-windows", 'exe': "realcugan-ncnn-vulkan.exe"},
        'python-fu-AIDenoise-RealESRGAN': {'MenuLabel': 'RealESRGAN', 'dir': "realesrgan-ncnn-vulkan-v0.2.0-windows", 'exe': "realesrgan-ncnn-vulkan.exe"},
        'python-fu-AIDenoise-SRMD': {'MenuLabel': 'SRMD', 'dir': "srmd-ncnn-vulkan-20220728-windows", 'exe': "srmd-ncnn-vulkan.exe" }  }

def commonProcess(model, procedure, run_mode, image, layers, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        GimpUi.init(model)
        dialog = GimpUi.ProcedureDialog.new(procedure, config)
        if config.find_property('model') != None:
            radio_frame = dialog.get_widget("model", GimpUi.IntRadioFrame)
            radio_frame.get_children()[0].set_orientation(Gtk.Orientation.HORIZONTAL)
        if config.find_property('noise') != None:
            if 'SRMD' in model:
                storeNoise = GimpUi.IntStore.new(["Off", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10" ])
            else:
                storeNoise = GimpUi.IntStore.new(["Off", "0", "1", "2", "3"])
            widgetNoise = dialog.get_int_radio("noise", storeNoise)
            widgetNoise.get_children()[0].set_orientation(Gtk.Orientation.HORIZONTAL)
            widgetNoise.show()
        if config.find_property('scale') != None:
            storeScale = GimpUi.IntStore.new([ "x2", "x3", "x4" ])
            widgetScale = dialog.get_int_radio("scale", storeScale)
            widgetScale.get_children()[0].set_orientation(Gtk.Orientation.HORIZONTAL)
            widgetScale.show()
        dialog.fill(None)
        dialog.set_position(Gtk.WindowPosition.CENTER)        
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()
    
    pdb = Gimp.get_pdb()
    Gimp.progress_init("Starting AI processing")
    
    # SAVE IMAGE AS PNG
    Gimp.progress_set_text("Saving image for processing")
    temp_file = tempfile.mktemp(suffix=".png")
    export_proc = pdb.lookup_procedure('file-png-export')
    cfg = export_proc.create_config()
    cfg.set_property('run-mode', Gimp.RunMode.NONINTERACTIVE)
    cfg.set_property('image', image)
    cfg.set_property('file', Gio.File.new_for_path(temp_file))
    export_proc.run(cfg)
    
    # PROCESS PNG
    Gimp.progress_set_text("Processing image")
    temp_scaled_file = tempfile.mktemp(suffix=".png")

    directory = os.path.join(os.path.dirname(os.path.realpath(__file__)), info[model]["dir"])
    arguments = [ os.path.join(directory, info[model]["exe"]), "-i", temp_file, "-o", temp_scaled_file ]
    if config.find_property('model') != None:
        if 'ESRGAN' in model:
            arguments += [ "-n", f"{config.get_property('model')}" ]
        else:
            arguments += [ "-m", f"models-{config.get_property('model')}" ]
    if config.find_property('noise') != None:
        arguments += [ "-n", f"{config.get_property('noise')-1}" ] # CONVERT 0 TO n INTO -1 TO n-1
    if config.find_property('scale') != None:
        arguments += [ "-s", f"{config.get_property('scale')+2}" ] # CONVERT 0 TO 2 INTO 2 TO 4
    if model == 'python-fu-AIDenoise-Waifu2x':
        arguments += [ "-s", "1" ]
        
    proc = subprocess.Popen( arguments, cwd=directory, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    os.set_blocking(proc.stderr.fileno(), False)
    allLog = ""
    while proc.poll() is None:
        output_line = proc.stderr.readline().decode('utf-8')
        allLog = allLog + output_line
        if "%" in output_line:
            Gimp.progress_set_text(f"{info[model]["MenuLabel"]} progress: {output_line}")
        time.sleep(0.1)
    if proc.returncode != 0:
        os.remove(temp_file)
        err = GLib.Error()
        err.message = f"Command: {" ".join(arguments)}\nOutput: {allLog}"
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, err)

    # LOAD 
    Gimp.progress_set_text("Loading processed image")
    load_proc = pdb.lookup_procedure('file-png-load')
    cfg = load_proc.create_config()
    cfg.set_property('run-mode', Gimp.RunMode.NONINTERACTIVE)
    cfg.set_property('file', Gio.File.new_for_path(temp_scaled_file))
    new_image = load_proc.run(cfg).index(1)

    # ADD LAYER WITH NEW IMAGE
    Gimp.progress_set_text("Creating layer")
    Gimp.context_set_interpolation(3)
    if "scale" in model.lower():
        image.scale(new_image.get_width(), new_image.get_height())
    else:
        new_image.scale(image.get_width(), image.get_height())
    layerName = f"{info[model]["MenuLabel"]}-{config.get_property('model')}" if config.find_property('model') != None else f"{info[model]["MenuLabel"]}"
    new_layer = Gimp.Layer.new_from_visible(new_image, image, layerName)
    image.insert_layer(new_layer, None, -1)
    
    # DELETE TEMPORARY FILES
    new_image.delete()
    os.remove(temp_file)
    os.remove(temp_scaled_file)

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

class AIProcess(Gimp.PlugIn):
    def do_set_i18n(self, procname):
        return True, 'gimp30-python', None

    def do_query_procedures(self):
        return [ k for k in info ]

    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, partial( commonProcess, name ), None)

        if 'RealSR' in name:
            model_choice = Gimp.Choice.new()
            model_choice.add("DF2K_JPEG", 0, "DF2K_JPEG", "")
            model_choice.add("DF2K", 1, "DF2K", "")
            procedure.add_choice_argument ("model", "Model", "Model", model_choice, "DF2K_JPEG", GObject.ParamFlags.READWRITE)
        elif 'Waifu2x' in name:
            model_choice = Gimp.Choice.new()
            model_choice.add("cunet", 0, "cunet", "")
            model_choice.add("upconv_7_anime_style_art_rgb", 1, "upconv_7_anime_style_art_rgb", "")
            model_choice.add("upconv_7_photo", 2, "upconv_7_photo", "")
            procedure.add_choice_argument ("model", "Model", "Model", model_choice, "cunet", GObject.ParamFlags.READWRITE)
            procedure.add_int_argument("noise", "Noise", "Noise", 0, 4, 0, GObject.ParamFlags.READWRITE)
        elif 'CUGAN' in name:
            model_choice = Gimp.Choice.new()
            model_choice.add("se", 0, "se", "")
            model_choice.add("pro", 1, "pro", "")
            model_choice.add("nose", 2, "nose", "")
            procedure.add_choice_argument ("model", "Model", "Model", model_choice, "se", GObject.ParamFlags.READWRITE)
            procedure.add_int_argument("noise", "Noise", "Noise", 0, 4, 0, GObject.ParamFlags.READWRITE)
            if "scale" in name.lower():
                procedure.add_int_argument("scale", "Scale", "Scale", 0, 2, 0, GObject.ParamFlags.READWRITE)
        elif 'ESRGAN' in name:
            model_choice = Gimp.Choice.new()
            model_choice.add("realesr-animevideov3", 0, "realesr-animevideov3", "")
            model_choice.add("realesrgan-x4plus", 1, "realesrgan-x4plus", "")
            model_choice.add("realesrgan-x4plus-anime", 2, "realesrgan-x4plus-anime", "")
            model_choice.add("AnimeSharp-4x", 3, "AnimeSharp-4x", "")
            model_choice.add("RealESRGAN_General_x4_v3", 4, "RealESRGAN_General_x4_v3", "")
            model_choice.add("UltraSharp-4x", 5, "UltraSharp-4x", "")
            procedure.add_choice_argument ("model", "Model", "Model", model_choice, "realesr-animevideov3", GObject.ParamFlags.READWRITE)
            if "scale" in name.lower():
                procedure.add_int_argument("scale", "Scale", "Scale", 0, 2, 0, GObject.ParamFlags.READWRITE)
        elif 'SRMD' in name:
            procedure.add_int_argument("noise", "Noise", "Noise", 0, 11, 0, GObject.ParamFlags.READWRITE)
            if "scale" in name.lower():
                procedure.add_int_argument("scale", "Scale", "Scale", 0, 2, 0, GObject.ParamFlags.READWRITE)
                               
        #COMMON
        procedure.set_menu_label(info[name]["MenuLabel"])
        if "scale" in name.lower():
            procedure.add_menu_path("<Image>/Filters/Cedrick/AI Scale/")
        else:
            procedure.add_menu_path("<Image>/Filters/Cedrick/AI Denoise/")
        procedure.set_image_types("*")
        procedure.set_documentation("Change the size of the image content with AI algorithms", globals()["__doc__"], name)
        procedure.set_attribution("Cedrick Collomb", "MIT License", "2025")
        
        return procedure
        
Gimp.main(AIProcess.__gtype__, sys.argv)
