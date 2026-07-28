#!/bin/bash

curl -X POST "http://localhost:8000/v1/chat/completions" \
	-H "Content-Type: application/json" \
    -H "Authorization: Bearer vllm-api-key" \
	--data '{
		"model": "qwen3-vl-32b-thinking",
		"messages": [
			{
				"role": "user",
				"content": [
					{
						"type": "text",
						"text": "Describe this image in one sentence."
					},
					{
						"type": "image_url",
						"image_url": {
							"url": "https://cdn.britannica.com/61/93061-050-99147DCE/Statue-of-Liberty-Island-New-York-Bay.jpg"
						}
					}
				]
			}
		]
	}'