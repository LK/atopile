# Global imports
import logging

from easyeda2kicad.easyeda.parameters_easyeda import (
    EasyedaPinType,
    EeSymbol,
)

ee_pin_type_to_ato_pin_type = {
    EasyedaPinType.unspecified: None,
    EasyedaPinType._input: "input",
    EasyedaPinType.output: "output",
    EasyedaPinType.bidirectional: "bidirectional",
    EasyedaPinType.power: "power",
}
ee_pin_rotation_to_vis_side = {
    0: "right",
    90: "bottom",
    180: "left",
    270: "top"
}
def add_pin_vis(name, pos):
    return f"""
  - name: {name}
    index: 0
    private: false
    port: {pos}"""

def convert_to_ato(ee_symbol: EeSymbol, component_id: str, component_name: str, footprint: str) -> str:
    ato_str = f"component {component_name}:\n"
    ato_str += f"    footprint = \"{footprint}\"\n"
    ato_str += f"    lcsc_id = \"{component_id}\"\n"
    ato_str += f"    # pins\n"
    ato_str_types = "    # pin types\n"
    ato_str_vis = """
STM32F103C8T6:
  ports:
  - name: top
    location: top
  - name: right
    location: right
  - name: left
    location: left
  - name: bottom
    location: bottom
  pins:"""
    for ee_pin in ee_symbol.pins:
        signal = ee_pin.name.text.replace(' ', '').replace('-', '_').replace('/', '_')
        pin = ee_pin.settings.spice_pin_number.replace(' ', '')
        ato_str += f"    signal {signal} ~ p{pin}\n"
        ato_pin_type = ee_pin_type_to_ato_pin_type[ee_pin.settings.type]
        if ato_pin_type:
            ato_str_types += f"    {signal}.type = {ato_pin_type}\n"
        location=ee_pin_rotation_to_vis_side[ee_pin.settings.rotation]
        ato_str_vis += add_pin_vis(signal, location)

    return ato_str + "\n" + ato_str_types, ato_str_vis

class ExporterAto:
    def __init__(self, symbol, component_id: str, component_name: str, footprint: str):
        self.input: EeSymbol = symbol
        self.output = (
            convert_to_ato(ee_symbol=self.input, component_id=component_id, component_name=component_name, footprint=footprint)
            if isinstance(self.input, EeSymbol)
            else logging.error("Unknown input symbol format")
        )

    def export(self, ato_full_path: str) -> str:
        print("################")
        print(ato_full_path)
        print("################")
        with open(
            file=ato_full_path,
            mode="w",
            encoding="utf-8",
        ) as my_lib:
            my_lib.write(self.output[0])
        ato_vis_path = ato_full_path.split('.ato')[0] + ".vis.yaml"
        print(ato_vis_path)
        print("################")
        with open(
            file=ato_vis_path,
            mode="w",
            encoding="utf-8",
        ) as my_lib:
            my_lib.write(self.output[1])
