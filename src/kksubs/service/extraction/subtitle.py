import logging
from typing import Dict, List, Set
from copy import deepcopy

from kksubs.data.subtitle.style_attributes import *
from kksubs.data.subtitle.style import Style
from kksubs.data.subtitle.subtitle import Subtitle, SubtitleGroup
# from kksubs.data.subtitle.subtitle import Background, BaseData, BoxData, Brightness, Gaussian, Mask, Motion, OutlineData, OutlineData1, Style, Subtitle, SubtitleGroup, TextData

# parsing/extraction, filtering, standardization
logger = logging.getLogger(__name__)

default_style_by_field_name:Dict[str, BaseData] = {
    base_data.field_name:base_data for base_data in [
        TextData, 
        OutlineData, 
        OutlineData1, 
        BoxData, 
        Asset,
        Brightness, 
        Gaussian, 
        Motion, 
        Background, 
        Mask,
        Style
    ]
}

def _is_valid_nested_attribute(style:BaseData, nested_attribute:str) -> bool:
    attributes = nested_attribute.split(".")
    if len(attributes) == 1:
        return hasattr(style, attributes[0])
    
    # check if attribute corresponds to a style.
    if attributes[0] in default_style_by_field_name.keys():
        return _is_valid_nested_attribute(default_style_by_field_name[attributes[0]](), ".".join(attributes[1:]))
    
    raise KeyError(style.field_name, nested_attribute)

def _give_attributes_to_style(base_style:Style, attributes:List[str], value):
    # print(attributes, type(base_style))
    
    if len(attributes) == 1:
        return setattr(base_style, attributes[0], value)
    
    if getattr(base_style, attributes[0]) is None:
        setattr(base_style, attributes[0], default_style_by_field_name[attributes[0]]())
    return _give_attributes_to_style(getattr(base_style, attributes[0]), attributes[1:], value)

def _add_data_to_style(line:str, subtitle:Subtitle, styles:Dict[str, Style]):
    # adds data to style.

    key, value = line.split(":", 1)
    value = value.strip()
    
    if key == "style_id":
        # replace style with style ID.
        subtitle.style = styles.get(value)
    
    else:
        attributes = key.split(".")
        _give_attributes_to_style(subtitle.style, attributes, value)

    pass

def _extract_subtitles_from_image_block(textstring:str, content_keys:Set[str], styles:Dict[str, Style]) -> List[Subtitle]:
    
    subtitles:List[Subtitle] = []
    lines = textstring.strip().split("\n")
    in_content_environment = False
    in_style_environment = False
    is_start_of_subtitle = True

    def get_has_content_key(line:str):
        return any(line.startswith(key+":") for key in content_keys)
    
    def get_has_attr_key(line:str):
        # print(line, line.split(":", 1))
        if len(line.split(":", 1)) == 2:
            # print("ping")
            return _is_valid_nested_attribute(default_style_by_field_name["style"](), line.split(":")[0])
        return False
        # return any(line.startswith(key+":") for key in style_keys)
    
    empty_lines:List[str]
    content:List[str]
    for i, line in enumerate(lines):
        # identify the start of a subtitle.

        has_content_key = get_has_content_key(line)
        has_style_key = get_has_attr_key(line)
        # has_next_line = i+1 <= len(lines)-1

        # state check.
        if not in_style_environment and has_style_key:
            is_start_of_subtitle = True
            in_content_environment = False
            in_style_environment = True
        elif not in_content_environment and has_content_key:
            is_start_of_subtitle = not in_style_environment or i==0
            in_style_environment = False
            in_content_environment = True
        elif in_content_environment and has_content_key:
            is_start_of_subtitle = True
        else:
            is_start_of_subtitle = False

        if is_start_of_subtitle:
            style = Style()
            content = []
            empty_lines = []
            subtitle = Subtitle(content=content, style=style)
            subtitles.append(subtitle)

        # content environment logic
        if in_content_environment:
            if has_content_key:
                lsplit = line.split(":", 1)
                if len(lsplit) == 2:
                    key, line_content = lsplit
                    if key == "content":
                        pass
                    else: # apply alias as style.
                        # deep copy to enforce independence between subtitle objects, esp. for child styles.
                        style.coalesce(deepcopy(styles.get(key)))
                else:
                    line_content = ""

                line_content = lsplit[1].lstrip() if len(lsplit) == 2 else ""
            else:
                line_content = line
            if not line_content:
                empty_lines.append(line_content)
            else:
                content += empty_lines
                empty_lines = []
                content.append(line_content)

        # style logic
        if in_style_environment:
            if has_style_key:
                _add_data_to_style(line, subtitle, styles)
            pass

        # print(
        #     int(is_start_of_subtitle), 
        #     int(in_content_environment),
        #     int(in_attr_environment),
        #     "line: ", line
        # )

    # correct subtitle styling data.
    for subtitle in subtitles:
        subtitle.style.coalesce(styles.get("default"))
        subtitle.style.coalesce(Style.get_default())
        subtitle.style.correct_values()

    # print(lines)
    # print(subtitles)
    return subtitles

def extract_subtitle_groups(
        draft_id:str, draft_body:str, styles:Dict[str, Style], image_dir:str, output_dir:str, prefix:str=None
) -> Dict[str, List[SubtitleGroup]]:
    # extract subtitle groups from draft
    logger.info(f"Extracting subtitle groups.")

    # subtitles = dict()
    subtitle_groups_by_image_id:Dict[str, List[SubtitleGroup]] = dict()
    content_keys = {"content"}.union(styles.keys())
    # remove comments
    draft_body = "\n".join(list(filter(lambda line:not line.startswith("#"), draft_body.split("\n"))))

    # split lines for draft
    image_blocks = draft_body.split("image_id:")

    for image_block in image_blocks:
        subtitle_groups:List[SubtitleGroup] = list()

        image_block = image_block.strip()
        if not image_block:
            continue

        # add subtitles.
        image_block_split = image_block.split("\n", 1)
        image_id = image_block_split[0].strip()

        if len(image_block_split) == 1:
            subtitle_group = SubtitleGroup(subtitles=list())
            subtitle_group.complete_path_info(draft_id, image_id, image_dir, output_dir, prefix=prefix)
            subtitle_group.subtitles.append(Subtitle([], style=Style.get_default().corrected()))
            subtitle_groups = [subtitle_group]

        else:
            
            # hide implementation
            lines = image_block_split[1].split('\n')
            if any(map(lambda i:'hide:' in lines, lines)):
                continue

            # sep implementation
            image_block_seps = image_block_split[1].split('sep:')
            if len(image_block_seps) <= 1:
                subtitle_group = SubtitleGroup(subtitles=list())
                subtitle_group.complete_path_info(draft_id, image_id, image_dir, output_dir)
                subtitle_group.subtitles = _extract_subtitles_from_image_block(image_block_seps[0], content_keys, styles)
                subtitle_groups.append(subtitle_group)
            else:
                for i, sep in enumerate(image_block_seps):
                    subtitle_group = SubtitleGroup(subtitles=list())
                    subtitle_group.complete_path_info(draft_id, image_id, image_dir, output_dir, prefix=prefix, suffix=f'_{i}')
                    subtitle_group.subtitles = _extract_subtitles_from_image_block(sep, content_keys, styles)
                    subtitle_groups.append(subtitle_group)

        subtitle_groups_by_image_id[image_id] = subtitle_groups

    return subtitle_groups_by_image_id