from rest_framework.pagination import PageNumberPagination

class CustomPageNumberPagination(PageNumberPagination):
    page_size = 10  # default page size
    page_size_query_param = 'page_size'  # client can override with ?page_size=
    max_page_size = 100  # prevent huge queries
